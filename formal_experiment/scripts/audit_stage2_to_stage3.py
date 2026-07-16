# -*- coding: utf-8 -*-
"""Stage 2 → Stage 3 compatibility audit (no LLM, no network).

Reads existing prediction JSONL files and checks whether each record
can be consumed by Sun's Stage 3 compliance checking pipeline.

Does NOT judge semantic correctness. Only checks structural readiness.

NB: this script is **not** strictly read-only — it writes its summary
report to `outputs/development/stage2_to_stage3_compat_audit_summary.json`
and `outputs/development/stage2_to_stage3_compat_audit_report.md`. It does
not modify the input prediction files, frozen input, frozen Gold, or
formal predictions/results; it only emits diagnostic artifacts under
`outputs/development/`.

Usage:
    python scripts/audit_stage2_to_stage3.py
    python scripts/audit_stage2_to_stage3.py --inputs file1.jsonl file2.jsonl
    python scripts/audit_stage2_to_stage3.py --output-dir <path>  # override
        the default `outputs/development` location
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter
from bpc_hybrid.sun_compat.schema import SunRuleRecord

# Default prediction files to audit
_DEFAULT_INPUTS = [
    "data/development/predictions/sun_rule_only.jsonl",
    "data/development/predictions/exploratory_spacy.jsonl",
    "data/development/predictions/sun_llm_fallback.jsonl",
]

_OUTPUT_DIR = _PROJECT_ROOT / "outputs" / "development"
_OUTPUT_JSON = _OUTPUT_DIR / "stage2_to_stage3_compat_audit_summary.json"
_OUTPUT_MD = _OUTPUT_DIR / "stage2_to_stage3_compat_audit_report.md"

# Thresholds for warnings
ACTION_MAX_LEN = 200  # chars — action longer than this may have leaked condition/constraint
CONDITION_MAX_LEN = 300
CONSTRAINT_MAX_LEN = 200
EXCEPTION_MAX_LEN = 200


def _get_field_value(pred: dict, field_name: str) -> str:
    """Extract field value from prediction, handling both nested and flat formats."""
    pf = pred.get("prediction_fields", {})
    val = pf.get(field_name)
    if isinstance(val, dict):
        return val.get("value", "") or ""
    if isinstance(val, str):
        return val
    return ""


def audit_single_prediction(adapter: ClauseAdapter, pred: dict, idx: int) -> dict:
    """Audit a single prediction record. Returns audit result dict."""
    sample_id = pred.get("sample_id", f"line_{idx+1}")
    method = pred.get("method", "unknown")
    result: dict = {
        "sample_id": sample_id,
        "method": method,
        "line_number": idx + 1,
        "json_valid": True,
        "convertible": False,
        "warnings": [],
        "errors": [],
        "field_coverage": {},
        "structural_flags": {},
    }

    # Extract fields
    modality = _get_field_value(pred, "modality")
    actor = _get_field_value(pred, "actor")
    action = _get_field_value(pred, "action")
    condition = _get_field_value(pred, "condition")
    constraint = _get_field_value(pred, "constraint")
    exception = _get_field_value(pred, "exception")
    source_text = pred.get("source_text", pred.get("text", ""))

    # Field coverage
    fields = {
        "modality": modality,
        "actor": actor,
        "action": action,
        "condition": condition,
        "constraint": constraint,
        "exception": exception,
    }
    result["field_coverage"] = {
        k: bool(v and v.strip()) for k, v in fields.items()
    }

    # Warnings: field quality
    if action and len(action) > ACTION_MAX_LEN:
        result["warnings"].append({
            "type": "action_too_long",
            "detail": f"action is {len(action)} chars (>{ACTION_MAX_LEN}), may have leaked condition/constraint",
            "value_preview": action[:120] + "...",
        })

    if condition and len(condition) > CONDITION_MAX_LEN:
        result["warnings"].append({
            "type": "condition_too_long",
            "detail": f"condition is {len(condition)} chars (>{CONDITION_MAX_LEN})",
            "value_preview": condition[:120] + "...",
        })

    if constraint and len(constraint) > CONSTRAINT_MAX_LEN:
        result["warnings"].append({
            "type": "constraint_too_long",
            "detail": f"constraint is {len(constraint)} chars (>{CONSTRAINT_MAX_LEN})",
            "value_preview": constraint[:120] + "...",
        })

    if exception and len(exception) > EXCEPTION_MAX_LEN:
        result["warnings"].append({
            "type": "exception_too_long",
            "detail": f"exception is {len(exception)} chars (>{EXCEPTION_MAX_LEN})",
            "value_preview": exception[:120] + "...",
        })

    # Check for action containing condition/constraint markers
    if action:
        action_lower = action.lower()
        cond_markers = ["if ", "when ", "where ", "unless ", "in the event"]
        for marker in cond_markers:
            if marker in action_lower:
                result["warnings"].append({
                    "type": "action_contains_condition_marker",
                    "detail": f"action contains '{marker.strip()}' — may have leaked from condition",
                })
                break

        constraint_markers = ["within ", "at least ", "no later than ", "not exceeding"]
        for marker in constraint_markers:
            if marker in action_lower:
                result["warnings"].append({
                    "type": "action_contains_constraint_marker",
                    "detail": f"action contains '{marker.strip()}' — may have leaked from constraint",
                })
                break

    # Check for missing actor
    if not actor or not actor.strip():
        result["warnings"].append({
            "type": "missing_actor",
            "detail": "actor is empty — actor_action_map cannot be generated",
        })

    # Check for missing action
    if not action or not action.strip():
        result["errors"].append({
            "type": "missing_action",
            "detail": "action is empty — cannot build obligation_lemmatized",
        })

    # Try conversion to Sun-compatible record
    try:
        record = adapter.convert(
            rule_id=sample_id,
            source_text=source_text,
            modality=modality or "unknown",
            actor=actor,
            action=action,
            condition=condition,
            constraint=constraint,
            exception=exception,
            provenance=method,
        )
        result["convertible"] = True

        # Structural flags
        obl = record.obligations[0] if record.obligations else None
        result["structural_flags"] = {
            "has_obligations": len(record.obligations) > 0,
            "has_obligation_lemmatized": bool(obl and obl.obligation_lemmatized),
            "has_actor_action_map": len(record.actor_action_maps) > 0,
            "has_order_relations": len(record.order_relations) > 0,
            "order_relation_count": len(obl.order_relations) if obl else 0,
            "validation_flags": obl.validation_flags if obl else {},
        }

        # Additional warnings from validation flags
        if obl and obl.validation_flags.get("action_too_long"):
            if not any(w["type"] == "action_too_long" for w in result["warnings"]):
                result["warnings"].append({
                    "type": "action_too_long_flag",
                    "detail": "ClauseAdapter flagged action as too long",
                })

        if not record.actor_action_maps:
            result["warnings"].append({
                "type": "no_actor_action_map",
                "detail": "Could not generate actor_action_map (missing actor or action)",
            })

        # Check JSON round-trip
        try:
            d = record.to_dict()
            json_str = json.dumps(d, ensure_ascii=False)
            SunRuleRecord.from_json(json_str)
        except Exception as e:
            result["errors"].append({
                "type": "round_trip_failed",
                "detail": str(e),
            })

    except Exception as e:
        result["errors"].append({
            "type": "conversion_failed",
            "detail": str(e),
        })

    return result


def audit_file(adapter: ClauseAdapter, filepath: Path) -> dict:
    """Audit all predictions in a JSONL file."""
    filename = filepath.name
    file_result = {
        "filename": filename,
        "path": str(filepath),
        "total_lines": 0,
        "valid_json_lines": 0,
        "invalid_json_lines": 0,
        "convertible_lines": 0,
        "records": [],
        "bad_lines": [],
        "summary": {},
    }

    if not filepath.exists():
        file_result["error"] = f"File not found: {filepath}"
        return file_result

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            file_result["total_lines"] += 1
            line = line.strip()
            if not line:
                continue

            try:
                pred = json.loads(line)
                file_result["valid_json_lines"] += 1
            except json.JSONDecodeError as e:
                file_result["invalid_json_lines"] += 1
                file_result["bad_lines"].append({
                    "line_number": i + 1,
                    "error": str(e),
                    "preview": line[:120],
                })
                continue

            record_audit = audit_single_prediction(adapter, pred, i)
            file_result["records"].append(record_audit)
            if record_audit["convertible"]:
                file_result["convertible_lines"] += 1

    # Compute summary
    total_warnings = sum(len(r["warnings"]) for r in file_result["records"])
    total_errors = sum(len(r["errors"]) for r in file_result["records"])
    warning_types: dict[str, int] = {}
    for r in file_result["records"]:
        for w in r["warnings"]:
            warning_types[w["type"]] = warning_types.get(w["type"], 0) + 1

    # Field coverage stats
    field_counts = {k: 0 for k in ["modality", "actor", "action", "condition", "constraint", "exception"]}
    for r in file_result["records"]:
        for k, v in r.get("field_coverage", {}).items():
            if v:
                field_counts[k] += 1
    n = max(file_result["valid_json_lines"], 1)
    field_coverage_pct = {k: round(v / n * 100, 1) for k, v in field_counts.items()}

    # Stage 3 readiness
    ready_for_stage3 = sum(
        1 for r in file_result["records"]
        if r["convertible"]
        and r.get("structural_flags", {}).get("has_obligations")
        and r.get("structural_flags", {}).get("has_obligation_lemmatized")
    )

    file_result["summary"] = {
        "valid_json_rate": round(file_result["valid_json_lines"] / max(file_result["total_lines"], 1) * 100, 1),
        "conversion_rate": round(file_result["convertible_lines"] / max(file_result["valid_json_lines"], 1) * 100, 1),
        "stage3_ready_rate": round(ready_for_stage3 / max(file_result["valid_json_lines"], 1) * 100, 1),
        "stage3_ready_count": ready_for_stage3,
        "total_warnings": total_warnings,
        "total_errors": total_errors,
        "warning_types": warning_types,
        "field_coverage_pct": field_coverage_pct,
    }

    return file_result


def generate_markdown_report(all_results: list[dict]) -> str:
    """Generate a Markdown audit report."""
    lines = [
        "# Stage 2 → Stage 3 Compatibility Audit Report",
        "",
        f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Tool**: `scripts/audit_stage2_to_stage3.py`",
        f"**Purpose**: Check whether existing Stage 2 predictions can be consumed by Sun's Stage 3 pipeline",
        "",
        "> This is a structural audit only. It does NOT judge semantic correctness.",
        "> It does NOT call any LLM, read .env, or access the network.",
        "",
        "---",
        "",
        "## Summary Table",
        "",
        "| File | Total | Valid JSON | Convertible | Stage3-Ready | Warnings | Errors |",
        "|------|-------|------------|-------------|--------------|----------|--------|",
    ]

    for r in all_results:
        s = r.get("summary", {})
        lines.append(
            f"| `{r['filename']}` | {r['total_lines']} | {r['valid_json_lines']} "
            f"| {r['convertible_lines']} | {s.get('stage3_ready_count', 0)} "
            f"| {s.get('total_warnings', 0)} | {s.get('total_errors', 0)} |"
        )

    lines.extend(["", "---", ""])

    # Per-file detail
    for r in all_results:
        lines.append(f"## `{r['filename']}`")
        lines.append("")
        s = r.get("summary", {})

        lines.append(f"- **Valid JSON rate**: {s.get('valid_json_rate', 0)}%")
        lines.append(f"- **Conversion rate**: {s.get('conversion_rate', 0)}%")
        lines.append(f"- **Stage 3 ready rate**: {s.get('stage3_ready_rate', 0)}%")
        lines.append("")

        # Field coverage
        lines.append("### Field Coverage")
        lines.append("")
        lines.append("| Field | Coverage |")
        lines.append("|-------|----------|")
        for k, v in s.get("field_coverage_pct", {}).items():
            lines.append(f"| {k} | {v}% |")
        lines.append("")

        # Bad lines
        if r.get("bad_lines"):
            lines.append("### Bad JSON Lines")
            lines.append("")
            for bl in r["bad_lines"]:
                lines.append(f"- **Line {bl['line_number']}**: `{bl['error']}`")
                lines.append(f"  Preview: `{bl['preview'][:100]}`")
            lines.append("")

        # Warning types
        wt = s.get("warning_types", {})
        if wt:
            lines.append("### Warning Types")
            lines.append("")
            lines.append("| Type | Count |")
            lines.append("|------|-------|")
            for wtype, count in sorted(wt.items(), key=lambda x: -x[1]):
                lines.append(f"| `{wtype}` | {count} |")
            lines.append("")

        # Sample warnings (first 5)
        sample_warnings = []
        for rec in r.get("records", []):
            for w in rec.get("warnings", []):
                sample_warnings.append({
                    "sample_id": rec["sample_id"],
                    **w,
                })
        if sample_warnings:
            lines.append("### Sample Warnings (first 10)")
            lines.append("")
            for sw in sample_warnings[:10]:
                lines.append(f"- **{sw['sample_id']}** [{sw['type']}]: {sw['detail']}")
                if "value_preview" in sw:
                    lines.append(f"  > `{sw['value_preview'][:100]}`")
            lines.append("")

        # Sample errors
        sample_errors = []
        for rec in r.get("records", []):
            for e in rec.get("errors", []):
                sample_errors.append({
                    "sample_id": rec["sample_id"],
                    **e,
                })
        if sample_errors:
            lines.append("### Errors")
            lines.append("")
            for se in sample_errors[:10]:
                lines.append(f"- **{se['sample_id']}** [{se['type']}]: {se['detail']}")
            lines.append("")

    # Route explanations
    lines.extend([
        "---",
        "",
        "## Two Optimization Routes",
        "",
        "### Route A: Sun-rule-first + LLM Fallback (Main Line)",
        "",
        "1. Run Sun-style rule extraction first (current pipeline).",
        "2. Identify fields that are empty or low-confidence.",
        "3. Call LLM ONLY to fill missing/low-confidence fields.",
        "4. LLM output must conform to Sun-compatible schema.",
        "5. Merge rule extraction + LLM fallback into final SunRuleRecord.",
        "",
        "**Key constraint**: LLM never overwrites high-confidence rule results.",
        "",
        "### Route B: Direct LLM Extraction (Control Experiment)",
        "",
        "1. Ask LLM to extract Sun-compatible rule record directly from raw text.",
        "2. No rule extraction step — LLM does everything.",
        "3. Output must be Sun-compatible schema (NOT Barrientos/RC4PC schema).",
        "4. If borrowing Barrientos prompt ideas, only borrow structured prompting, validation, and normalization, not the output format.",
        "",
        "**Key constraint**: Final output must be SunRuleRecord, not Winter-style dict.",
        "",
        "---",
        "",
        "## Known Issues",
        "",
        "The following items are **historical** notes carried over from earlier",
        "experiments. Verify each reference still exists before acting on it.",
        "",
        "1. Winter-style mapping should NOT be the final interface — only used as intermediate heuristic.",
        "2. Action fields that are too long (>200 chars) may indicate condition/constraint leakage.",
        "",
        "Run `audit_project.py --with-tests` for the current, machine-checked",
        "list of known issues; do not rely on the historical list above as",
        "evidence of an active bug.",
    ])

    return "\n".join(lines)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Stage 2 → Stage 3 compatibility audit")
    parser.add_argument("--inputs", nargs="*", default=None, help="JSONL files to audit")
    args = parser.parse_args()

    input_paths = []
    if args.inputs:
        input_paths = [Path(p) for p in args.inputs]
    else:
        input_paths = [_PROJECT_ROOT / p for p in _DEFAULT_INPUTS]

    print("=" * 60)
    print("Stage 2 → Stage 3 Compatibility Audit")
    print("=" * 60)
    print(f"  Files to audit: {len(input_paths)}")
    for p in input_paths:
        print(f"    - {p.name}")
    print()

    # Initialize adapter (spaCy loaded once)
    print("  Initializing spaCy...")
    adapter = ClauseAdapter()
    print()

    all_results = []
    for filepath in input_paths:
        print(f"Auditing: {filepath.name}")
        result = audit_file(adapter, filepath)
        all_results.append(result)

        s = result.get("summary", {})
        print(f"  Total lines: {result['total_lines']}")
        print(f"  Valid JSON: {result['valid_json_lines']} ({s.get('valid_json_rate', 0)}%)")
        print(f"  Bad JSON: {result['invalid_json_lines']}")
        print(f"  Convertible: {result['convertible_lines']} ({s.get('conversion_rate', 0)}%)")
        print(f"  Stage 3 Ready: {s.get('stage3_ready_count', 0)} ({s.get('stage3_ready_rate', 0)}%)")
        print(f"  Warnings: {s.get('total_warnings', 0)}")
        print(f"  Errors: {s.get('total_errors', 0)}")
        if result.get("bad_lines"):
            print(f"  Bad lines: {[bl['line_number'] for bl in result['bad_lines']]}")
        print()

    # Write JSON summary
    _OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "files_audited": len(all_results),
            "results": all_results,
        }, f, indent=2, ensure_ascii=False)
    print(f"JSON summary: {_OUTPUT_JSON}")

    # Write Markdown report
    _OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md_content = generate_markdown_report(all_results)
    with open(_OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Markdown report: {_OUTPUT_MD}")

    print()
    print("Audit complete.")


if __name__ == "__main__":
    main()

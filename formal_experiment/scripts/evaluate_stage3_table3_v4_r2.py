# -*- coding: utf-8 -*-
"""Independent R2 evaluator for the scoped Table 3 benchmark.

It reuses the frozen R1 evaluator for metric formulas and hash/unique-key
checks, then adds R2-only exact ID-set validation and non-scoring order-signal
diagnostics.  The reference is opened only after all output/manifest checks
have passed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

R2_CONFIG = ROOT / "configs/stage3_table3_v4_execution_r2.json"
R2_OUT_DIR = ROOT / "outputs/development/stage3_table3_v4_r2"
REFERENCE = ROOT / "data/development/stage3_reconstruction_v4/construction_reference.json"
INFERENCE_VIEW = ROOT / "data/development/stage3_reconstruction_v4/inference_view.json"
R2_REPORT_JSON = ROOT / "outputs/reports/stage3_table3_v4_r2.json"
R2_REPORT_MD = ROOT / "outputs/reports/stage3_table3_v4_r2.md"
R2_REPORT_MANIFEST = ROOT / "outputs/reports/stage3_table3_v4_r2.manifest.json"


def _load_r1_evaluator() -> Any:
    path = ROOT / "scripts/evaluate_stage3_table3_v4_r1.py"
    spec = importlib.util.spec_from_file_location("stage3_table3_v4_r1_evaluator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R1 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _exact_id_contract() -> dict[str, Any]:
    cfg = _load_json(R2_CONFIG)
    view = _load_json(INFERENCE_VIEW)
    expected_case_ids = sorted({str(item["case_id"]) for item in view.get("items") or []})
    expected_rule_ids = sorted({str(rule_id) for rule_id in (cfg.get("scope") or {}).get("rule_ids") or []})
    if len(expected_case_ids) != 20 or len(expected_rule_ids) != 5:
        raise RuntimeError("frozen id contract is not 20 unique cases / 5 unique rules")
    return {"cfg": cfg, "expected_case_ids": expected_case_ids,
            "expected_rule_ids": expected_rule_ids}


def _validate_exact_id_sets(predictions: Mapping[str, Any], run_manifest: Mapping[str, Any],
                            expected_case_ids: list[str], expected_rule_ids: list[str]) -> dict[str, Any]:
    rows = list(predictions.get("records") or [])
    actual_case_ids = sorted({str(row.get("case_id")) for row in rows})
    if actual_case_ids != expected_case_ids:
        raise RuntimeError(f"prediction case-id set does not equal frozen inference_view set: "
                           f"{actual_case_ids} != {expected_case_ids}")
    method_case_ids: dict[str, set[str]] = {}
    for row in rows:
        method = str(row.get("row_method_id"))
        method_case_ids.setdefault(method, set()).add(str(row.get("case_id")))
        signals = row.get("signals_by_rule") or {}
        if sorted(str(k) for k in signals) != expected_rule_ids:
            raise RuntimeError(f"prediction rule-id set drift for {method}/{row.get('case_id')}")
    for method, case_ids in method_case_ids.items():
        if sorted(case_ids) != expected_case_ids:
            raise RuntimeError(f"method {method} does not cover exact frozen case-id set")
    if sorted(str(x) for x in run_manifest.get("actual_output_case_ids") or []) != expected_case_ids:
        raise RuntimeError("run manifest actual_output_case_ids does not equal frozen inference_view set")
    if sorted(str(x) for x in run_manifest.get("actual_output_rule_ids") or []) != expected_rule_ids:
        raise RuntimeError("run manifest actual_output_rule_ids does not equal frozen rule-id set")
    return {"case_ids": actual_case_ids, "rule_ids": expected_rule_ids,
            "method_case_id_sets": {k: sorted(v) for k, v in method_case_ids.items()}}


def _augment_report(report: dict[str, Any], predictions: Mapping[str, Any],
                    rule_records: Mapping[str, Any]) -> dict[str, Any]:
    nested: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for row in predictions.get("records") or []:
        for rid, checks in (row.get("signals_by_rule") or {}).items():
            for check_type, signal in (checks or {}).items():
                nested[(str(row.get("row_method_id")), str(row.get("case_id")),
                        str(rid), str(check_type))] = signal
    ref_by_key: dict[tuple[str, str, str, str], str] = {}
    for ev in report.get("evidence") or []:
        key = (str(ev.get("method")), str(ev.get("case_id")),
               str(ev.get("rule_id")), str(ev.get("check_type")))
        ref_by_key[key] = str(ev.get("reference"))
        if ev.get("check_type") != "out_of_order":
            continue
        signal = nested.get(key) or {}
        diag = signal.get("order_diagnostic") or {}
        ev["order_diagnostic_category"] = diag.get("category")
        ev["order_diagnostic"] = diag
        ev["raw_reason"] = signal.get("raw_reason", signal.get("reason"))
    category_counts: dict[str, dict[str, int]] = {}
    records: list[dict[str, Any]] = []
    method_rule_records = {
        method: (block or {}).get("records") or {}
        for method, block in (rule_records or {}).items()
    }
    for row in predictions.get("records") or []:
        method = str(row.get("row_method_id"))
        case_id = str(row.get("case_id"))
        for rid, checks in sorted((row.get("signals_by_rule") or {}).items()):
            signal = (checks or {}).get("out_of_order") or {}
            diag = signal.get("order_diagnostic") or {}
            category = str(diag.get("category") or signal.get("reason") or "unknown")
            category_counts.setdefault(method, {})
            category_counts[method][category] = category_counts[method].get(category, 0) + 1
            rule_record = (method_rule_records.get(method) or {}).get(str(rid)) or {}
            records.append({
                "method": method,
                "case_id": case_id,
                "rule_id": str(rid),
                "reference": ref_by_key.get((method, case_id, str(rid), "out_of_order")),
                "predicted_status": signal.get("status"),
                "raw_score": signal.get("raw_score"),
                "denominator": signal.get("denominator"),
                "reason": signal.get("reason"),
                "raw_reason": signal.get("raw_reason", signal.get("reason")),
                "failure_category": category,
                "order_relation_count": len(rule_record.get("order_relations") or []),
                "order_relation_projection": rule_record.get("order_relation_projection"),
                "order_diagnostic": diag,
            })
    report.setdefault("diagnostics", {})
    report["diagnostics"]["order_failure_category_counts"] = category_counts
    report["diagnostics"]["order_failure_category_records"] = records
    report["order_failure_category_summary"] = category_counts
    return report


def _append_markdown(md_path: Path, report: Mapping[str, Any], id_checks: Mapping[str, Any]) -> None:
    existing = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    lines = [existing.rstrip(), "", "## R2 exact ID-set check", ""]
    lines.append(f"- case IDs equal frozen inference_view: `{id_checks['case_ids']}`")
    lines.append(f"- rule IDs equal frozen input set: `{id_checks['rule_ids']}`")
    lines.append("")
    lines.append("## R2 order failure categories")
    lines.append("")
    lines.append("| Method | Category | Count |")
    lines.append("|---|---|---:|")
    for method in ("sun", "ours", "winter"):
        for category, count in sorted((report.get("order_failure_category_summary") or {}).get(method, {}).items()):
            lines.append(f"| {method} | {category} | {count} |")
    lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def evaluate(*, out_dir: Path = R2_OUT_DIR, report_json: Path = R2_REPORT_JSON,
             report_md: Path = R2_REPORT_MD,
             report_manifest: Path = R2_REPORT_MANIFEST) -> dict[str, Any]:
    id_contract = _exact_id_contract()
    r1 = _load_r1_evaluator()
    r1.CONFIG = R2_CONFIG
    r1.OUT_DIR = out_dir
    r1.REPORT_JSON = report_json
    r1.REPORT_MD = report_md
    r1.REPORT_MANIFEST = report_manifest

    predictions = _load_json(out_dir / "predictions.json")
    run_manifest = _load_json(out_dir / "run_manifest.json")
    id_checks = _validate_exact_id_sets(predictions, run_manifest,
                                        id_contract["expected_case_ids"],
                                        id_contract["expected_rule_ids"])
    report = r1.evaluate(out_dir=out_dir, report_json=report_json,
                         report_md=report_md, report_manifest=report_manifest)
    rule_records = _load_json(out_dir / "rule_records.json")
    report = _augment_report(report, predictions, rule_records)
    report["exact_id_set_checks"] = id_checks
    _write_json(report_json, report)
    _append_markdown(report_md, report, id_checks)
    manifest = {
        "schema_version": "stage3_table3_v4_r2_report_manifest@1.0.0",
        "status": report.get("status"),
        "inputs": report.get("source_hashes") or {},
        "outputs": {
            "json": {"path": report_json.relative_to(ROOT).as_posix(),
                     "sha256": _sha_file(report_json)},
            "markdown": {"path": report_md.relative_to(ROOT).as_posix(),
                         "sha256": _sha_file(report_md)},
        },
        "counts": {
            method: {
                "overall_cells": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("cells"),
                "not_applicable_cells": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("not_applicable_cells"),
                "tp": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("tp"),
                "fp": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("fp"),
                "fn": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("fn"),
                "tn": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("tn"),
                "unknown_positive": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("unknown_positive"),
                "unknown_negative": ((report.get("methods") or {}).get(method) or {}).get("overall", {}).get("unknown_negative"),
            } for method in ("sun", "ours", "winter")
        },
        "acceptance": report.get("status"),
        "gold_read": False,
        "no_prediction_modification": True,
    }
    _write_json(report_manifest, manifest)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=R2_OUT_DIR)
    parser.add_argument("--report-json", type=Path, default=R2_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=R2_REPORT_MD)
    parser.add_argument("--report-manifest", type=Path, default=R2_REPORT_MANIFEST)
    args = parser.parse_args()
    report = evaluate(out_dir=args.out_dir, report_json=args.report_json,
                      report_md=args.report_md, report_manifest=args.report_manifest)
    print(json.dumps({
        "status": report.get("status"),
        "acceptance": (report.get("diagnostics") or {}).get("acceptance"),
        "flags": (report.get("diagnostics") or {}).get("flags"),
        "order_failure_category_summary": report.get("order_failure_category_summary"),
        "outputs": {
            "json": args.report_json.relative_to(ROOT).as_posix(),
            "markdown": args.report_md.relative_to(ROOT).as_posix(),
            "manifest": args.report_manifest.relative_to(ROOT).as_posix(),
        },
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

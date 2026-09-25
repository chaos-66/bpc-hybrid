# -*- coding: utf-8 -*-
"""Independent R3 evaluator wrapper.

It reuses the frozen R1/R2 evaluator implementation (formulas, unknown and
coverage rules, exact case/rule ID checks, nested/flat consistency) and only
rebinds the R3 config/output/report paths.  The reference is opened by the
wrapped evaluator after the saved predictions and manifest SHA bindings have
passed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

DEFAULT_CONFIG = ROOT / "configs/stage3_table3_r3_m1.json"
DEFAULT_OUT_DIR = ROOT / "outputs/development/stage3_table3_r3_m1"
DEFAULT_REPORT_JSON = ROOT / "outputs/reports/stage3_table3_r3_m1.json"
DEFAULT_REPORT_MD = ROOT / "outputs/reports/stage3_table3_r3_m1.md"
DEFAULT_REPORT_MANIFEST = ROOT / "outputs/reports/stage3_table3_r3_m1.manifest.json"


def _sha_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _load_r2_evaluator():
    path = ROOT / "scripts/evaluate_stage3_table3_v4_r2.py"
    spec = importlib.util.spec_from_file_location("stage3_table3_v4_r2_evaluator_for_r3", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load R2 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate(*, config_path: Path = DEFAULT_CONFIG, out_dir: Path = DEFAULT_OUT_DIR,
             report_json: Path = DEFAULT_REPORT_JSON,
             report_md: Path = DEFAULT_REPORT_MD,
             report_manifest: Path = DEFAULT_REPORT_MANIFEST) -> dict:
    r2 = _load_r2_evaluator()
    r2.R2_CONFIG = config_path
    r2.R2_OUT_DIR = out_dir
    r2.R2_REPORT_JSON = report_json
    r2.R2_REPORT_MD = report_md
    r2.R2_REPORT_MANIFEST = report_manifest
    report = r2.evaluate(out_dir=out_dir, report_json=report_json,
                         report_md=report_md, report_manifest=report_manifest)
    report = _load_json(report_json)
    cfg = _load_json(config_path)
    backend = (cfg.get("similarity") or {}).get("backend")
    report["schema_version"] = "stage3_table3_r3_report@1.0.0"
    report["report_version"] = "R3"
    report["r3_context"] = {
        "task_id": cfg.get("task_id"),
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": _sha_file(config_path),
        "similarity_backend": backend,
        "temporal_projection": (cfg.get("temporal_projection") or {}).get("algorithm"),
        "p2_adapter": (cfg.get("p2_adapter") or {}).get("adapter_module"),
        "development_status": cfg.get("development_status"),
    }
    _write_json(report_json, report)

    report_manifest_doc = {
        "schema_version": "stage3_table3_r3_report_manifest@1.0.0",
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
        "backend": backend,
    }
    _write_json(report_manifest, report_manifest_doc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--report-manifest", type=Path, default=DEFAULT_REPORT_MANIFEST)
    args = parser.parse_args()
    report = evaluate(config_path=args.config, out_dir=args.out_dir,
                      report_json=args.report_json, report_md=args.report_md,
                      report_manifest=args.report_manifest)
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

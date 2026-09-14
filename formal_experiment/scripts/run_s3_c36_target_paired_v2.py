# -*- coding: utf-8 -*-
"""Gated S3-C36-TARGET-PAIRED successor runner (zero API).

The runner reads the frozen C36/Winter predictions and the current v5
predictions, then applies the v2 compatibility gate before any comparison is
written.  A failed gate writes a blocked report only; no valid comparison
artifact is produced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s3_c36_target_paired_v2 import (  # noqa: E402
    BASELINE_NAME,
    REVISION,
    audit_gate,
    compare_target_paired_gated,
    derive_target_paired_rows,
    read_json,
    read_jsonl,
    sha256_file,
    sha256_file_canonical_lf,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
C36_EVIDENCE = ROOT / "outputs/evidence/s3_formula_repair_v2"
C36_PREDICTIONS = C36_EVIDENCE / "extended_four/reference/winter/predictions.jsonl"
C36_MANIFEST = C36_EVIDENCE / "manifest.json"
C36_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
V5_PREDICTIONS = ROOT / "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
V5_MANIFEST = ROOT / "outputs/evidence/s3_semantic_grounding_v5/manifest.json"
V5_ARTIFACT_HASHES = ROOT / "outputs/evidence/s3_semantic_grounding_v5/artifact_hashes.json"
OUT_DIR = ROOT / "outputs/evidence/s3_c36_target_paired_v2"
REPORT_JSON = ROOT / "outputs/reports/s3_c36_target_paired_v2.json"
REPORT_MD = ROOT / "outputs/reports/s3_c36_target_paired_v2.md"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def render_markdown(comparison: Mapping[str, Any], audit: Mapping[str, Any]) -> str:
    baseline = comparison["c36_winter_style_baseline"]
    current = comparison["current_v5"]
    deps = audit["dependency_bindings"]
    dep = deps["control_reconstruction"]
    lines = [
        "# S3-C36-TARGET-PAIRED v2 (gated, development-only, zero API)",
        "",
        f"Baseline: **{BASELINE_NAME}**.  This is not a direct Winter paper result.",
        "兼容性检查通过后才生成比较；control 侧布尔值已持久化在 80 条检查记录中，",
        "不需要再次写文件来产生独立证据。",
        "",
        "## Compatibility gate",
        "",
        f"- Gate status: **{audit['gate_status']}**",
        f"- Blocking issues: **{audit['blocking_issue_count']}**",
        f"- Reconstruction dependency verified frozen match: "
        f"**{dep['verified_frozen_match']}**",
        f"- Dependency verification basis: `{dep['verification_basis']}`",
        f"- Frozen gamma_ext: **{audit['threshold_binding']['frozen_manifest_gamma_ext']}**",
        "",
        "## Target-paired comparison",
        "",
        "| Method | Macro-F1 | Pair success | Target unknown | Control target FP |",
        "|---|---:|---:|---:|---:|",
        f"| {BASELINE_NAME} | {baseline['target_paired_macro_f1_four_types']:.4f} | "
        f"{baseline['pair_success_count']}/{baseline['pair_success_denominator']} | "
        f"{baseline['target_field_unknown_rate_all_side_checks']:.4f} | "
        f"{baseline['control_target_false_positive_rate_all_pairs']:.4f} |",
        f"| Current v5 deterministic | {current['target_paired_macro_f1_four_types']:.4f} | "
        f"{current['pair_success_count']}/{current['pair_success_denominator']} | "
        f"{current['target_field_unknown_rate_all_side_checks']:.4f} | "
        f"{current['control_target_false_positive_rate_all_pairs']:.4f} |",
        "",
        "## Per-type checks",
        "",
        "| Type | Baseline F1 | v5 F1 | Baseline variant TP/FNobs/FNunk | v5 variant TP/FNobs/FNunk | Baseline control TN/FP/unknown | v5 control TN/FP/unknown |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for target in baseline["per_type"]:
        b = baseline["per_type"][target]
        v = current["per_type"][target]
        lines.append(
            f"| {target} | {b['f1']:.4f} | {v['f1']:.4f} | "
            f"{b['variant']['TP']}/{b['variant']['FN_observed_negative']}/{b['variant']['unknown']} | "
            f"{v['variant']['TP']}/{v['variant']['FN_observed_negative']}/{v['variant']['unknown']} | "
            f"{b['control']['TN']}/{b['control']['FP']}/{b['control']['unknown']} | "
            f"{v['control']['TN']}/{v['control']['FP']}/{v['control']['unknown']} |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- Development-only synthetic controlled panel; not formal Oracle or human Gold.",
        "- Expected labels are used only after fixed predictions for evaluation grouping.",
        "- Control-side final booleans are reconstructed from the frozen C36 score fields; "
        "they are now persisted in the v2 80-row check artifact.",
        "- No historical prediction, manifest or Gold was modified; real API calls = 0.",
        "",
    ]
    return "\n".join(lines)


def _blocked_report(audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "s3_c36_target_paired_report@2.0.0",
        "revision": REVISION,
        "status": "BLOCKED_COMPATIBILITY_AUDIT",
        "scope": "development_only_synthetic_panel",
        "baseline_name": BASELINE_NAME,
        "valid_comparison_generated": False,
        "blocking_issue_count": audit["blocking_issue_count"],
        "blocking_issue_codes": audit["blocking_issue_codes"],
        "audit": audit,
        "claim_boundary": (
            "No valid target-paired comparison was generated because the "
            "compatibility gate failed."),
    }


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (OUT_DIR, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing v2 outputs")
    panel = read_json(PANEL)
    c36_rows = read_jsonl(C36_PREDICTIONS)
    current_rows = read_jsonl(V5_PREDICTIONS)
    c36_manifest = read_json(C36_MANIFEST)
    c36_report = read_json(C36_REPORT)
    current_artifact_hashes = read_json(V5_ARTIFACT_HASHES)

    audit = audit_gate(
        c36_rows=c36_rows, panel=panel, current_rows=current_rows,
        c36_manifest=c36_manifest,
        current_artifact_hashes=current_artifact_hashes,
        current_predictions_path=V5_PREDICTIONS,
        c36_predictions_path=C36_PREDICTIONS,
        c36_report=c36_report, root=ROOT)

    if not audit["can_build_target_paired"]:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        write_json(OUT_DIR / "blocked_audit.json", audit)
        report = _blocked_report(audit)
        write_json(REPORT_JSON, report)
        REPORT_MD.write_text(
            "# S3-C36-TARGET-PAIRED v2 blocked\n\n"
            f"Status: **{report['status']}**\n\n"
            f"Blocking issues: **{audit['blocking_issue_count']}**\n\n"
            f"Codes: `{audit['blocking_issue_codes']}`\n",
            encoding="utf-8", newline="\n")
        return {"status": "blocked", "audit": audit, "report": report}

    c36_target_rows = derive_target_paired_rows(c36_rows)
    comparison = compare_target_paired_gated(c36_target_rows, current_rows, panel)
    manifest = {
        "schema_version": "s3_c36_target_paired_manifest@2.0.0",
        "run_id": REVISION,
        "revision": REVISION,
        "base_revision": "s3_c36_target_paired_v1",
        "scope": "development_only",
        "baseline_name": BASELINE_NAME,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "panel": {
            "path": PANEL.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(PANEL),
            "panel_id": panel.get("panel_id") or panel.get("schema_version"),
            "variant_count": len(panel.get("variants", [])),
        },
        "inputs": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (PANEL, INFERENCE_PACK, C36_PREDICTIONS, C36_MANIFEST,
                         C36_REPORT, V5_PREDICTIONS, V5_MANIFEST,
                         V5_ARTIFACT_HASHES)
            if path.is_file()
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                Path(__file__),
                ROOT / "src/bpc_hybrid/s3_c36_target_paired_v2.py",
                ROOT / "src/bpc_hybrid/s3_c36_target_paired_v1.py",
                ROOT / "tests/test_s3_c36_target_paired_v2.py",
            ) if path.is_file()
        },
        "compatibility_gate": {
            "status": audit["gate_status"],
            "can_build_target_paired": audit["can_build_target_paired"],
            "blocking_issue_count": audit["blocking_issue_count"],
            "blocking_issue_codes": audit["blocking_issue_codes"],
        },
        "dependency_bindings": audit["dependency_bindings"],
        "threshold_binding": audit["threshold_binding"],
        "manifest_input_checks": audit["manifest_input_checks"],
        "prediction_identity": {
            "c36": audit["c36_prediction_identity"],
            "current_v5": audit["current_prediction_identity"],
        },
        "control_reconstruction": {
            "required": True,
            "rule": audit["control_reconstruction_rule"],
            "affected_control_samples": audit["affected_control_samples"],
            "affected_control_checks": audit["affected_control_checks"],
            "booleans_persisted_in_output_rows": True,
        },
        "comparison_summary": {
            "baseline": comparison["c36_winter_style_baseline"],
            "current_v5": comparison["current_v5"],
            "delta_current_minus_baseline": comparison[
                "delta_current_minus_baseline"],
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "historical_c36_outputs_overwritten": False,
            "historical_v5_outputs_overwritten": False,
            "development_only_not_formal_oracle": True,
        },
    }
    report = {
        "schema_version": "s3_c36_target_paired_report@2.0.0",
        "revision": REVISION,
        "status": "VERIFIED_DEVELOPMENT_COMPARISON_V2",
        "scope": "development_only_synthetic_panel",
        "baseline_name": BASELINE_NAME,
        "audit": audit,
        "comparison": comparison,
        "manifest": manifest,
        "claim_boundary": (
            "Development-only synthetic controlled panel. The baseline is a "
            "Winter-style four-type extension baseline, not a direct Winter "
            "paper result. Control booleans are reconstructed from frozen C36 "
            "fields and persisted in the v2 80-row check artifact. No formal "
            "Oracle, human Gold or real API run is claimed."),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_DIR / "audit.json", audit)
    write_jsonl(OUT_DIR / "c36_winter_target_paired_checks.jsonl", c36_target_rows)
    write_json(OUT_DIR / "comparison.json", comparison)
    write_json(OUT_DIR / "manifest.json", manifest)
    write_json(REPORT_JSON, report)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_markdown(comparison, audit),
                         encoding="utf-8", newline="\n")
    artifacts = [
        OUT_DIR / "audit.json",
        OUT_DIR / "c36_winter_target_paired_checks.jsonl",
        OUT_DIR / "comparison.json",
        OUT_DIR / "manifest.json",
        REPORT_JSON,
        REPORT_MD,
    ]
    write_json(OUT_DIR / "artifact_hashes.json", {
        "schema_version": "s3_c36_target_paired_artifact_hashes@2.0.0",
        "revision": REVISION,
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in artifacts
        },
    })
    return {"status": "verified", "audit": audit,
            "comparison": comparison, "manifest": manifest, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    if result["status"] == "blocked":
        print(json.dumps({
            "revision": REVISION,
            "status": "BLOCKED_COMPATIBILITY_AUDIT",
            "blocking_issue_count": result["audit"]["blocking_issue_count"],
            "blocking_issue_codes": result["audit"]["blocking_issue_codes"],
            "real_api_calls": 0,
        }, ensure_ascii=False, indent=2))
        return 2
    comparison = result["comparison"]
    print(json.dumps({
        "revision": REVISION,
        "status": "VERIFIED_DEVELOPMENT_COMPARISON_V2",
        "baseline_name": BASELINE_NAME,
        "baseline_macro_f1": comparison[
            "c36_winter_style_baseline"]["target_paired_macro_f1_four_types"],
        "current_macro_f1": comparison["current_v5"][
            "target_paired_macro_f1_four_types"],
        "baseline_pair_success": comparison[
            "c36_winter_style_baseline"]["pair_success_count"],
        "current_pair_success": comparison["current_v5"]["pair_success_count"],
        "control_reconstruction_verified": result["audit"][
            "dependency_bindings"]["control_reconstruction"][
                "verified_frozen_match"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

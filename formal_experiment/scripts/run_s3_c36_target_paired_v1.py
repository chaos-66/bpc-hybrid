# -*- coding: utf-8 -*-
"""Generate S3-C36-TARGET-PAIRED artifacts (offline, zero API).

Inputs are the frozen C36/Winter variant prediction file and the frozen
current v5 predictions.  The script:
1. audits item coverage, labels, process/rule ids and BPMN hashes;
2. audits per-check field coverage and control-side reconstruction dependency;
3. expands C36 rows into variant/control target-paired checks;
4. compares C36/Winter with the current v5 method under one target-paired
   protocol and writes new revision artifacts/reports only.
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

from bpc_hybrid.s3_c36_target_paired_v1 import (  # noqa: E402
    REVISION,
    audit_c36_winter,
    compare_target_paired,
    derive_target_paired_rows,
    read_json,
    read_jsonl,
    sha256_file,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
C36_EVIDENCE = ROOT / "outputs/evidence/s3_formula_repair_v2"
C36_PREDICTIONS = C36_EVIDENCE / "extended_four/reference/winter/predictions.jsonl"
C36_MANIFEST = C36_EVIDENCE / "manifest.json"
C36_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
V5_PREDICTIONS = ROOT / "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
V5_MANIFEST = ROOT / "outputs/evidence/s3_semantic_grounding_v5/manifest.json"
OUT_DIR = ROOT / "outputs/evidence/s3_c36_target_paired_v1"
REPORT_JSON = ROOT / "outputs/reports/s3_c36_target_paired_v1.json"
REPORT_MD = ROOT / "outputs/reports/s3_c36_target_paired_v1.md"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def render_markdown(comparison: Mapping[str, Any], audit: Mapping[str, Any]) -> str:
    c36 = comparison["c36_winter"]
    cur = comparison["current_v5"]
    lines = [
        "# S3-C36-TARGET-PAIRED (development-only, zero API)",
        "",
        "冻结 C36/Winter 原始预测与当前 v5 预测在**同一 target-paired 口径**下的比较。",
        "C36 control 侧没有持久化布尔 `violation`，本比较使用项目冻结函数",
        "`stage3_extended_violations.control_prediction_from_scores` 从已保存的 per-check",
        "`observable/score/reason/exact_contradiction` 字段重建，未使用任何统一单标签预测，",
        "也未使用 Gold/expected label 生成预测。",
        "",
        "## Compatibility audit",
        "",
        f"- C36 item ids equal panel: **{audit['sample_sets']['c36_item_ids_equal_panel']}**",
        f"- label/process/BPMN hash issues: **{len(audit['label_issues'])}/"
        f"{len(audit['process_issues'])}/{len(audit['c36_variant_bpmn_hash_issues'])}/"
        f"{len(audit['c36_control_bpmn_hash_issues'])}**",
        f"- variant field gaps: **{sum(1 for x in audit['field_gaps'] if x['scope']=='variant')}**",
        f"- control reconstruction: **{audit['control_reconstruction_rule']}**",
        f"- can build target-paired comparison: **{audit['can_build_target_paired']}**",
        "",
        "## Target-paired comparison",
        "",
        "| Method | Macro-F1 | Pair success | Unknown rate | Control target FP rate |",
        "|---|---|---|---|---|",
        f"| C36/Winter (control reconstructed) | {c36['target_paired_macro_f1_four_types']:.4f} | "
        f"{c36['pair_success_count']}/{c36['pair_success_denominator']} = "
        f"{c36['pair_success_rate']:.4f} | "
        f"{c36['target_field_unknown_rate_all_side_checks']:.4f} | "
        f"{c36['control_target_false_positive_rate_all_pairs']:.4f} |",
        f"| Current v5 deterministic | {cur['target_paired_macro_f1_four_types']:.4f} | "
        f"{cur['pair_success_count']}/{cur['pair_success_denominator']} = "
        f"{cur['pair_success_rate']:.4f} | "
        f"{cur['target_field_unknown_rate_all_side_checks']:.4f} | "
        f"{cur['control_target_false_positive_rate_all_pairs']:.4f} |",
        "",
        "## Per-type checks",
        "",
        "| Type | C36 F1 | v5 F1 | C36 variant TP/FNobs/FNunk | v5 variant TP/FNobs/FNunk | C36 control TN/FP/unknown | v5 control TN/FP/unknown |",
        "|---|---|---|---|---|---|---|",
    ]
    for target in comparison["c36_winter"]["per_type"]:
        c = c36["per_type"][target]
        v = cur["per_type"][target]
        lines.append(
            f"| {target} | {c['f1']:.4f} | {v['f1']:.4f} | "
            f"{c['variant']['TP']}/{c['variant']['FN_observed_negative']}/{c['variant']['unknown']} | "
            f"{v['variant']['TP']}/{v['variant']['FN_observed_negative']}/{v['variant']['unknown']} | "
            f"{c['control']['TN']}/{c['control']['FP']}/{c['control']['unknown']} | "
            f"{v['control']['TN']}/{v['control']['FP']}/{v['control']['unknown']} |"
        )
    lines += [
        "",
        "## Boundary",
        "",
        "- Panel: development-only synthetic controlled panel `synthetic_controlled_error_extension_v2`.",
        "- Same 40 variant/control pairs and same frozen rule/process inputs (manifest input hashes match).",
        "- C36 variant checks are explicit in `scores_detail`; C36 control checks are reconstructed by the frozen project rule.",
        "- No Gold, historical prediction, or existing artifact was modified; real API calls = 0.",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (OUT_DIR, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing S3-C36-TARGET-PAIRED outputs")
    panel = read_json(PANEL)
    c36_rows = read_jsonl(C36_PREDICTIONS)
    current_rows = read_jsonl(V5_PREDICTIONS)
    c36_manifest = read_json(C36_MANIFEST)
    c36_manifest["_root"] = str(ROOT)
    c36_report = read_json(C36_REPORT)

    audit = audit_c36_winter(
        c36_rows, panel, c36_manifest=c36_manifest,
        current_rows=current_rows, c36_report=c36_report)
    c36_target_rows = derive_target_paired_rows(c36_rows)
    comparison = compare_target_paired(c36_target_rows, current_rows, panel)

    field_gaps_path = OUT_DIR / "field_gaps.json"
    field_gaps = {
        "schema_version": "s3_c36_target_paired_field_gaps@1.0.0",
        "revision": REVISION,
        "field_gaps": audit["field_gaps"],
        "control_reconstruction_rule": audit["control_reconstruction_rule"],
        "control_reconstruction_required": audit["control_reconstruction_required"],
        "affected_control_samples": audit["affected_control_samples"],
        "affected_control_checks": audit["affected_control_checks"],
        "blocking_gap_count": sum(
            1 for gap in audit["field_gaps"] if gap.get("severity") == "blocking"),
        "single_label_inference_used": False,
    }
    manifest = {
        "schema_version": "s3_c36_target_paired_manifest@1.0.0",
        "run_id": REVISION,
        "revision": REVISION,
        "scope": "development_only",
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
                         C36_REPORT, V5_PREDICTIONS, V5_MANIFEST)
            if path.is_file()
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                Path(__file__),
                ROOT / "src/bpc_hybrid/s3_c36_target_paired_v1.py",
                ROOT / "tests/test_s3_c36_target_paired_v1.py",
            ) if path.is_file()
        },
        "audit_summary": {
            "can_build_target_paired": audit["can_build_target_paired"],
            "sample_sets": audit["sample_sets"],
            "field_gap_count": len(audit["field_gaps"]),
            "blocking_field_gap_count": field_gaps["blocking_gap_count"],
            "control_reconstruction_required": audit["control_reconstruction_required"],
            "control_reconstruction_rule": audit["control_reconstruction_rule"],
            "affected_control_samples": audit["affected_control_samples"],
            "affected_control_checks": audit["affected_control_checks"],
            "unified_single_label_ignored_for_derivation": True,
        },
        "comparison_summary": {
            "c36_winter": comparison["c36_winter"],
            "current_v5": comparison["current_v5"],
            "delta_current_minus_c36": comparison["delta_current_minus_c36"],
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
        "schema_version": "s3_c36_target_paired_report@1.0.0",
        "revision": REVISION,
        "status": "VERIFIED_DEVELOPMENT_COMPARISON",
        "scope": "development_only_synthetic_panel",
        "audit": audit,
        "comparison": comparison,
        "field_gaps": field_gaps,
        "manifest": manifest,
        "claim_boundary": (
            "Development-only synthetic panel. C36 control-side target checks are "
            "reconstructed from frozen control_scores by the documented project rule; "
            "no formal Oracle, human Gold, or real API run is claimed."),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(OUT_DIR / "audit.json", audit)
    write_jsonl(OUT_DIR / "c36_winter_target_paired_checks.jsonl", c36_target_rows)
    write_json(OUT_DIR / "comparison.json", comparison)
    write_json(field_gaps_path, field_gaps)
    write_json(OUT_DIR / "manifest.json", manifest)
    write_json(REPORT_JSON, report)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(render_markdown(comparison, audit),
                         encoding="utf-8", newline="\n")
    artifacts = [
        OUT_DIR / "audit.json",
        OUT_DIR / "c36_winter_target_paired_checks.jsonl",
        OUT_DIR / "comparison.json",
        field_gaps_path,
        OUT_DIR / "manifest.json",
        REPORT_JSON,
        REPORT_MD,
    ]
    write_json(OUT_DIR / "artifact_hashes.json", {
        "schema_version": "s3_c36_target_paired_artifact_hashes@1.0.0",
        "revision": REVISION,
        "artifacts": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in artifacts
        },
    })
    return {"audit": audit, "comparison": comparison,
            "field_gaps": field_gaps, "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    c36 = result["comparison"]["c36_winter"]
    current = result["comparison"]["current_v5"]
    print(json.dumps({
        "revision": REVISION,
        "can_build_target_paired": result["audit"]["can_build_target_paired"],
        "c36_macro_f1": c36["target_paired_macro_f1_four_types"],
        "c36_pair_success": f"{c36['pair_success_count']}/{c36['pair_success_denominator']}",
        "current_macro_f1": current["target_paired_macro_f1_four_types"],
        "current_pair_success": f"{current['pair_success_count']}/{current['pair_success_denominator']}",
        "control_reconstruction_rule": result["audit"][
            "control_reconstruction_rule"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

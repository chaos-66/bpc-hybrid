# -*- coding: utf-8 -*-
"""SEP-C4 v7 candidate: evidence-eligible anchor consensus (zero real API).

Reuses the frozen v2 predictions and panel BPMN.  Rebuilds each Process Record
with the same lightweight reader as the committed v6 runner, verifies the
rebuilt checker inputs against the Stage-1 derived compact context stored in
the frozen v2 predictions, re-decides saved candidates with
``s3_semantic_grounding_v7``, and writes a new artifact set without touching
the committed v6 outputs.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
for _candidate in (ROOT / "src", ROOT / "scripts"):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import run_sep_c4_action_anchor_scope_v1 as base  # noqa: E402

from bpc_hybrid.s3_semantic_grounding_v2 import build_compact_local_context  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v7 import (  # noqa: E402
    REVISION,
    disambiguate_action_grounding,
    score_sentence,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

PANEL = base.PANEL
V2_PREDICTIONS = base.V2_PREDICTIONS
V5_PREDICTIONS = base.V5_PREDICTIONS
V6_PREDICTIONS = (ROOT / "outputs/evidence/sep_c4_action_anchor_scope_v1"
                  / "predictions.jsonl")
V6_ARTIFACT_HASHES = (ROOT / "outputs/evidence/sep_c4_action_anchor_scope_v1"
                      / "artifact_hashes.json")

EVIDENCE_DIR = ROOT / "outputs/evidence/sep_c4_action_anchor_scope_v2"
DEVELOPMENT_DIR = ROOT / "outputs/development/sep_c4_action_anchor_scope_v2"
REPORT_JSON = ROOT / "outputs/reports/sep_c4_action_anchor_scope_v2.json"
REPORT_MD = ROOT / "outputs/reports/sep_c4_action_anchor_scope_v2.md"
RUN_ID = "sep_c4_action_anchor_scope_v2"

FOUR_EXCEPTION_ITEMS = (
    "syn_v2_exception_not_handled_04",
    "syn_v2_exception_not_handled_07",
    "syn_v2_exception_not_handled_08",
    "syn_v2_exception_not_handled_09",
)


def _canonical_lf_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def verify_v6_predictions() -> dict[str, Any]:
    expected = (base.read_json(V6_ARTIFACT_HASHES).get("artifacts") or {}).get(
        "outputs/evidence/sep_c4_action_anchor_scope_v1/predictions.jsonl")
    raw = base.sha256_file(V6_PREDICTIONS)
    canonical_lf = _canonical_lf_sha256(V6_PREDICTIONS)
    return {
        "available": True,
        "path": V6_PREDICTIONS.relative_to(ROOT).as_posix(),
        "expected_sha256": expected,
        "actual_raw_sha256": raw,
        "actual_canonical_lf_sha256": canonical_lf,
        "match": bool(expected) and expected in {raw, canonical_lf},
    }


def _checker_context_matches(record, xml_root, ground, checks, stored) -> bool:
    return build_compact_local_context(record, xml_root, ground, checks) == stored


def build_rows(panel: Mapping[str, Any], base_rows: Sequence[Mapping[str, Any]]
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                          dict[str, Any], list[dict[str, Any]]]:
    by_item = {item["variant_id"]: item for item in panel["variants"]}
    bpmn_cache: dict[str, Any] = {}
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    verified_bpmn: set[str] = set()
    mismatches: list[dict[str, Any]] = []
    context_checked = 0
    for row in base_rows:
        item_id = str(row.get("item_id") or "")
        side = str(row.get("side") or "")
        variant = by_item.get(item_id)
        if variant is None:
            raise RuntimeError(f"row item_id not present in panel: {item_id}")
        rel_path = str(variant.get(f"{side}_bpmn") or "")
        if not rel_path:
            raise RuntimeError(f"{item_id}:{side} has no BPMN path")
        path = ROOT / rel_path
        expected_hash = str(variant.get(f"{side}_bpmn_sha256") or "")
        raw_hash = base.sha256_file(path)
        canonical_lf = _canonical_lf_sha256(path)
        if expected_hash and expected_hash not in {raw_hash, canonical_lf}:
            raise RuntimeError(f"BPMN hash mismatch: {rel_path}")
        verified_bpmn.add(rel_path)
        cache_key = path.as_posix()
        if cache_key not in bpmn_cache:
            bpmn_cache[cache_key] = base.read_bpmn(path)
        record, xml_root, _ = bpmn_cache[cache_key]

        old_ground = row.get("action_grounding") or {}
        old_checks = row.get("checks") or {}
        context_checked += 1
        if not _checker_context_matches(record, xml_root, old_ground,
                                        old_checks,
                                        row.get("compact_local_context") or {}):
            mismatches.append({"item_id": item_id, "side": side,
                               "bpmn": rel_path})

        new_ground = disambiguate_action_grounding(old_ground)
        score = score_sentence(row.get("model_visible_rule_input") or {},
                               record, xml_root, new_ground)
        new_row = copy.deepcopy(dict(row))
        new_row.update({
            "schema_version": "s3_semantic_grounding_v7_prediction@1.0.0",
            "revision": REVISION,
            "action_grounding": new_ground,
            "action_anchor_consistency": score.get("action_anchor_consistency"),
            "anchor_guard_changes": score.get("anchor_guard_changes"),
            "checks": score.get("checks"),
            "decision": score.get("decision"),
            "predicted_violation_type": (score.get("decision") or {}).get("predicted"),
            "scores": score.get("scores"),
            "observability": score.get("observability"),
        })
        output.append(new_row)
        changes.append(base.build_change_record(row, new_row))
    coverage = {
        "panel_variants": len(panel["variants"]),
        "base_rows": len(base_rows),
        "variant_rows": sum(1 for row in base_rows if row.get("side") == "variant"),
        "control_rows": sum(1 for row in base_rows if row.get("side") == "control"),
        "unique_bpmn_paths_verified": len(verified_bpmn),
        "record_context_checked": context_checked,
        "record_context_matched": context_checked - len(mismatches),
        "record_context_mismatches": len(mismatches),
        "model_similarity_recomputed": False,
        "model_inference_calls": 0,
        "real_api_calls": 0,
        "network_calls": 0,
        "saved_candidates_reused": True,
    }
    return output, changes, coverage, mismatches


def _outcome(check: Mapping[str, Any]) -> str:
    if check.get("violation") is True:
        return "positive"
    if check.get("observable") is True and check.get("violation") is False:
        return "negative"
    return "unknown"


def build_four_exception_review(v6_rows, v7_rows) -> list[dict[str, Any]]:
    v6_by = {(r.get("item_id"), r.get("side")): r for r in v6_rows}
    v7_by = {(r.get("item_id"), r.get("side")): r for r in v7_rows}
    review: list[dict[str, Any]] = []
    for item_id in FOUR_EXCEPTION_ITEMS:
        key = (item_id, "variant")
        before = v6_by.get(key) or {}
        after = v7_by.get(key) or {}
        bg = before.get("action_grounding") or {}
        ag = after.get("action_grounding") or {}
        be = (bg.get("disambiguation") or {}).get("effective_support") or {}
        ae = (ag.get("disambiguation") or {}).get("effective_support") or {}
        bc = (before.get("checks") or {}).get("exception_not_handled") or {}
        ac = (after.get("checks") or {}).get("exception_not_handled") or {}
        review.append({
            "item_id": item_id,
            "side": "variant",
            "expected_label": before.get("expected_label"),
            "v6": {
                "action_status": bg.get("status"),
                "effective_support_size": len(be),
                "outcome": _outcome(bc),
                "status": bc.get("status"),
                "observable": bc.get("observable"),
                "violation": bc.get("violation"),
                "reason": bc.get("reason"),
                "action_grounding_status": bc.get("action_grounding_status"),
                "predicted": before.get("predicted_violation_type"),
            },
            "v7": {
                "action_status": ag.get("status"),
                "effective_support_size": len(ae),
                "outcome": _outcome(ac),
                "status": ac.get("status"),
                "observable": ac.get("observable"),
                "violation": ac.get("violation"),
                "reason": ac.get("reason"),
                "action_grounding_status": ac.get("action_grounding_status"),
                "predicted": after.get("predicted_violation_type"),
            },
        })
    return review


def _change_counts(changes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    changed_rows = [c for c in changes if c.get("changed")]
    action_change_count = sum(1 for c in changed_rows
                              if c["action_grounding"]["identity_changed"])
    action_reason_change_count = sum(1 for c in changes
                                     if c["action_grounding"]["reason_changed"])
    check_change_count: dict[str, int] = {}
    check_reason_change_count: dict[str, int] = {}
    for change in changes:
        for target in change.get("checks", {}):
            if target in change.get("check_reason_only_changes", {}):
                check_reason_change_count[target] = (
                    check_reason_change_count.get(target, 0) + 1)
                continue
            check_change_count[target] = check_change_count.get(target, 0) + 1
    return {
        "total_rows": len(changes),
        "changed_row_count": len(changed_rows),
        "action_change_count": action_change_count,
        "action_reason_change_count": action_reason_change_count,
        "check_change_count_by_target": check_change_count,
        "check_reason_only_change_count_by_target": check_reason_change_count,
        "changed_rows": changed_rows,
    }


def render_markdown(metrics: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    before = metrics["baseline_v2"]
    v6 = metrics["baseline_v6"]
    after = metrics["candidate_v7"]
    lines = [
        "# SEP-C4 anchor/evidence-scope repaired candidate v2 (v7 eligible consensus)",
        "",
        "`s3_semantic_grounding_v7` fixes the committed v6 bug where retrieved",
        "candidates without effective grounding evidence were merged into a",
        "definite violation. Frozen v2 saved candidates/similarities and panel",
        "BPMN are reused. real API=0, no model inference, no similarity recompute.",
        "The committed v6 artifacts are not overwritten.",
        "",
        "## Process Record checker-context consistency",
        "",
        f"- Checker-used compact local context: **"
        f"{manifest['record_context_consistency']['matched']}/"
        f"{manifest['record_context_consistency']['checked']}** rows identical to the",
        f"Stage-1 derived v2 context; mismatches="
        f"{manifest['record_context_consistency']['mismatches']}.",
        "- Compared fields: nodes / sequence flows / condition / constraint / exception evidence.",
        "- Stage-1 parse contract unchanged.",
        "",
        "## Four-type target-paired results (40 pairs / 80 rows, full denominator)",
        "",
        "| Type | V7 variant TP/FN_obs/FN_unknown | V7 control TN/FP/unknown | V7 F1 | V6 F1 | V2 F1 | Pair success |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for target in EXTENDED_TYPES:
        row = after["per_type"][target]
        row_v6 = v6["per_type"][target]
        row_v2 = before["per_type"][target]
        lines.append(
            f"| {target} | {row['variant']['TP']}/"
            f"{row['variant']['FN_observed_negative']}/{row['variant']['FN_unknown']} | "
            f"{row['control']['TN']}/{row['control']['FP']}/{row['control']['unknown']} | "
            f"{row['f1']} | {row_v6['f1']} | {row_v2['f1']} | "
            f"{row['pair_success']}/{row['pairs']} |")
    lines += [
        "",
        f"- V7 target-paired macro-F1: **{after['macro_f1_four_types']}**",
        f"- V6 candidate macro-F1: **{v6['macro_f1_four_types']}**",
        f"- V2 baseline macro-F1: **{before['macro_f1_four_types']}**",
        f"- V7 pair success: **{after['pair_success']}/40** ({after['pair_success_rate']})",
        f"- V7 target-field unknown rate: **{after['target_field_unknown_rate']}**",
        f"- V7 control target-field FP rate: **{after['control_target_false_positive_rate']}**",
        "",
        "## Fate of the four v6 exception TPs",
        "",
        "| Item | v6 effective_support | V6 outcome/violation | V6 lower action status | V7 outcome/violation | V7 reason |",
        "|---|---|---|---|---|---|",
    ]
    for item in metrics["four_exception_tp_review"]:
        lines.append(
            f"| {item['item_id']} | {item['v6']['effective_support_size']} | "
            f"{item['v6']['outcome']}/{item['v6']['violation']} | "
            f"{item['v6']['action_grounding_status']} | "
            f"{item['v7']['outcome']}/{item['v7']['violation']} | "
            f"{item['v7']['reason']} |")
    lines += [
        "",
        "All four rows had `effective_support={}` in v6 but were merged into",
        "`not_handled` because every retrieved candidate lacked a handler. v7 sees",
        "no evidence-eligible candidate and returns `unknown`; they are no longer TP.",
        "",
        "## TP / unknown / control FP change (v6 -> v7)",
        "",
    ]
    for target in EXTENDED_TYPES:
        delta = metrics["outcome_deltas_from_v6"][target]
        lines.append(
            f"- {target}: variant TP {delta['variant_tp_before']}->"
            f"{delta['variant_tp_after']}; lost {delta['variant_tp_lost_items']}; "
            f"gained {delta['variant_tp_gained_items']}; variant unknown "
            f"{delta['variant_unknown_before']}->{delta['variant_unknown_after']}; "
            f"control FP {delta['control_fp_before']}->{delta['control_fp_after']}; "
            f"control unknown {delta['control_unknown_before']}->"
            f"{delta['control_unknown_after']}")
    lines += ["", "## TP / unknown / control FP change (v2 -> v7)", ""]
    for target in EXTENDED_TYPES:
        delta = metrics["outcome_deltas_v2_to_v7"][target]
        lines.append(
            f"- {target}: variant TP {delta['variant_tp_before']}->"
            f"{delta['variant_tp_after']}; variant unknown "
            f"{delta['variant_unknown_before']}->{delta['variant_unknown_after']}; "
            f"control FP {delta['control_fp_before']}->{delta['control_fp_after']}; "
            f"control unknown {delta['control_unknown_before']}->"
            f"{delta['control_unknown_after']}")
    lines += [
        "",
        "## Row-level changes",
        "",
        f"- Changed rows (v2 -> v7): **{metrics['changes']['changed_row_count']}** / "
        f"**{metrics['changes']['total_rows']}**",
        "",
        "## Boundary",
        "",
        "- When grounding is ambiguous and `effective_support` is empty, definite",
        "  condition/constraint/exception verdicts stay unknown; missing local",
        "  structure in a retrieved candidate is not treated as an anchor fact.",
        "- Evidence-eligible candidates still reach a defined verdict when their",
        "  observed candidate scopes agree; disagreement/incomplete surface stays unknown.",
        "- Unique exact match, resolved single-anchor evidence, unreachable-evidence",
        "  isolation and the prohibited existence check are unchanged.",
        "- Upstream action extraction, abstract constraint semantics, the Stage 2",
        "  validator and the Stage 3 prompt are out of scope this round.",
        "- An F1 drop (if any) withdraws unsupported TPs; it is not a repair failure.",
        "  This candidate does not claim a proven performance improvement.",
        "",
        "## Sources",
        "",
        f"- v2 predictions SHA-256: `{manifest['inputs']['v2_predictions']['actual_raw_sha256']}`",
        f"- v6 predictions SHA-256: `{manifest['inputs']['v6_predictions']['actual_raw_sha256']}`",
        f"- panel SHA-256: `{manifest['inputs']['panel']}`",
        f"- implementation: `{manifest['implementation']}`",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (EVIDENCE_DIR, DEVELOPMENT_DIR,
                                      REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing SEP-C4 v7 candidate outputs")
    reuse = base.verify_v2_predictions()
    if not reuse["match"]:
        raise RuntimeError("v2 predictions hash mismatch; refusing to reuse")
    v6_reuse = verify_v6_predictions()
    if not v6_reuse["match"]:
        raise RuntimeError("v6 predictions hash mismatch; refusing comparison")
    v5_reuse = base._verify_optional_v5_predictions()
    panel = base.read_json(PANEL)
    base_rows = base.read_rows(V2_PREDICTIONS)
    v6_rows = base.read_rows(V6_PREDICTIONS)
    expected_by_item = {item["variant_id"]: item["expected_violation"]
                        for item in panel["variants"]}

    candidate_rows, changes, coverage, mismatches = build_rows(panel, base_rows)
    if mismatches:
        raise RuntimeError("rebuilt checker context differs from Stage-1 context: "
                           f"{mismatches[:3]}")
    candidate_paired = base._paired_from_rows(candidate_rows, expected_by_item)
    base_paired = base._paired_from_rows(base_rows, expected_by_item)
    v6_paired = base._paired_from_rows(v6_rows, expected_by_item)
    baseline_v5 = None
    if v5_reuse.get("available") and v5_reuse.get("match"):
        v5_rows = base.read_rows(V5_PREDICTIONS)
        baseline_v5 = base.build_summary(
            base._paired_from_rows(v5_rows, expected_by_item))

    metrics_changes = _change_counts(changes)
    four_review = build_four_exception_review(v6_rows, candidate_rows)
    manifest = {
        "schema_version": "sep_c4_action_anchor_scope_manifest@2.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "base_revision": "s3_semantic_grounding_v6",
        "scope": "development_only_candidate",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "v2_predictions": reuse,
            "v6_predictions": v6_reuse,
            "panel": base.sha256_file(PANEL),
            "v5_predictions_for_comparison": v5_reuse,
        },
        "implementation": {
            "module": "src/bpc_hybrid/s3_semantic_grounding_v7.py",
            "module_sha256": base.sha256_file(
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_v7.py"),
            "base_module": "src/bpc_hybrid/s3_semantic_grounding_v6.py",
            "base_module_sha256": base.sha256_file(
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_v6.py"),
            "runner": "scripts/run_sep_c4_action_anchor_scope_v2.py",
            "runner_sha256": base.sha256_file(Path(__file__)),
            "tests": "tests/test_s3_semantic_grounding_v7.py",
            "tests_sha256": base.sha256_file(
                ROOT / "tests/test_s3_semantic_grounding_v7.py"),
        },
        "record_context_consistency": {
            "checked": coverage["record_context_checked"],
            "matched": coverage["record_context_matched"],
            "mismatches": coverage["record_context_mismatches"],
            "method": "build_compact_local_context(rebuilt) == stored v2 compact_local_context",
        },
        "coverage": coverage,
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "model_inference_calls": 0,
            "model_similarity_recomputed": False,
            "historical_predictions_overwritten": False,
            "historical_v6_outputs_overwritten": False,
            "thresholds_changed": False,
            "gold_modified": False,
            "panel_modified": False,
        },
        "new_output_paths": {
            "evidence": EVIDENCE_DIR.relative_to(ROOT).as_posix(),
            "development": DEVELOPMENT_DIR.relative_to(ROOT).as_posix(),
            "report_json": REPORT_JSON.relative_to(ROOT).as_posix(),
            "report_md": REPORT_MD.relative_to(ROOT).as_posix(),
        },
    }
    metrics = {
        "schema_version": "sep_c4_action_anchor_scope_metrics@2.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only_candidate",
        "read_only_reuse": reuse,
        "v6_read_only_reuse": v6_reuse,
        "real_api_calls": 0,
        "network_calls": 0,
        "model_inference_calls": 0,
        "candidate_v7": base.build_summary(candidate_paired),
        "baseline_v6": base.build_summary(v6_paired),
        "baseline_v2": base.build_summary(base_paired),
        "baseline_v5": baseline_v5,
        "target_paired_candidate_v7": candidate_paired,
        "target_paired_baseline_v6": v6_paired,
        "target_paired_baseline_v2": base_paired,
        "outcome_deltas_from_v6": base.outcome_deltas(
            v6_rows, candidate_rows, expected_by_item),
        "outcome_deltas_v2_to_v7": base.outcome_deltas(
            base_rows, candidate_rows, expected_by_item),
        "four_exception_tp_review": four_review,
        "changes": metrics_changes,
    }
    report = {
        "schema_version": "sep_c4_action_anchor_scope_report@2.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "status": "CANDIDATE_OFFLINE_REPLAY_CONSISTENCY_FIX",
        "claim_boundary": (
            "Development-only frozen-panel replay. The v6 empty-effective-support "
            "bug is fixed and covered by semantic counterexample tests. Unsupported "
            "v6 TPs are withdrawn to unknown; F1 is not required to increase and this "
            "candidate is not a proven performance improvement. No real API/model "
            "inference/similarity recomputation. v6 artifacts are retained."),
        "manifest": manifest,
        "metrics": metrics,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    DEVELOPMENT_DIR.mkdir(parents=True, exist_ok=True)
    base.write_rows(EVIDENCE_DIR / "predictions.jsonl", candidate_rows)
    base.write_rows(DEVELOPMENT_DIR / "predictions.jsonl", candidate_rows)
    base.write_json(EVIDENCE_DIR / "change_report.json", metrics_changes)
    base.write_json(DEVELOPMENT_DIR / "change_report.json", metrics_changes)
    base.write_json(EVIDENCE_DIR / "metrics.json", metrics)
    base.write_json(DEVELOPMENT_DIR / "metrics.json", metrics)
    base.write_json(EVIDENCE_DIR / "manifest.json", manifest)
    base.write_json(DEVELOPMENT_DIR / "manifest.json", manifest)
    base.write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(metrics, manifest), encoding="utf-8",
                         newline="\n")

    artifact_paths = [
        EVIDENCE_DIR / "predictions.jsonl", EVIDENCE_DIR / "change_report.json",
        EVIDENCE_DIR / "metrics.json", EVIDENCE_DIR / "manifest.json",
        DEVELOPMENT_DIR / "predictions.jsonl", DEVELOPMENT_DIR / "change_report.json",
        DEVELOPMENT_DIR / "metrics.json", DEVELOPMENT_DIR / "manifest.json",
        REPORT_JSON, REPORT_MD,
    ]
    base.write_json(EVIDENCE_DIR / "artifact_hashes.json", {
        "schema_version": "sep_c4_action_anchor_scope_artifact_hashes@2.0.0",
        "run_id": RUN_ID,
        "artifacts": {path.relative_to(ROOT).as_posix(): base.sha256_file(path)
                      for path in artifact_paths},
    })
    return {"metrics": metrics, "manifest": manifest, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    after = metrics["candidate_v7"]
    print(json.dumps({
        "revision": REVISION,
        "target_paired_macro_f1": after["macro_f1_four_types"],
        "v6_macro_f1": metrics["baseline_v6"]["macro_f1_four_types"],
        "pair_success": f"{after['pair_success']}/40",
        "target_field_unknown_rate": after["unknown_rate_variant"],
        "control_target_fp_rate": after["control_false_positive_rate"],
        "record_context_matched": metrics["candidate_v7"] is not None,
        "changed_rows_vs_v2": metrics["changes"]["changed_row_count"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Deterministic runner for revision s3_semantic_grounding_v2.

It reuses the frozen v1 deterministic scorer, but applies the corrected v2
evaluation protocol (target-paired causal, composite-input collision audit,
offline control-global-compliance status, clean unified subset) and freezes a
Gold-blind fallback candidate pack.  No real LLM/API call is made here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import spacy  # noqa: E402

from bpc_hybrid.s3_semantic_grounding_v1 import (  # noqa: E402
    SemanticGroundingScorer,
    fold_whitespace,
)
from bpc_hybrid.s3_semantic_grounding_v2 import (  # noqa: E402
    CONTROL_GLOBAL_VERIFIED,
    REVISION,
    audit_composite_collisions,
    build_clean_control_set,
    build_compact_local_context,
    build_fallback_pack,
    control_global_compliance_status,
    evaluate_target_paired,
    evaluate_unified_objects,
    evaluate_variant_binary,
    fallback_triggers,
    input_identity,
    unified_objects_clean,
    unified_objects_legacy,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_bytes  # noqa: E402
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    extract_six_element_sentences,
    sentence_matches_locked,
)
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
V2_CONFIG = ROOT / "configs/stage3_semantic_grounding_v2.json"
V1_REPORT = ROOT / "outputs/reports/s3_semantic_grounding_v1.json"
V1_MANIFEST = ROOT / "outputs/evidence/s3_semantic_grounding_v1/manifest.json"
C36_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
C36_MANIFEST = ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json"
SUN_SCORER = ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py"

OUT_DIR = ROOT / "outputs/development/s3_semantic_grounding_v2"
EVIDENCE_DIR = ROOT / "outputs/evidence/s3_semantic_grounding_v2"
REPORT_JSON = ROOT / "outputs/reports/s3_semantic_grounding_v2.json"
REPORT_MD = ROOT / "outputs/reports/s3_semantic_grounding_v2.md"
FALLBACK_PACK_NAME = "llm_fallback_candidate_pack_v1.json"
RUN_ID = "s3_semantic_grounding_v2"
EVALUATOR_VERSION = "s3_semantic_grounding_v2_evaluator@1.0.0"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return {"commit": commit, "dirty": bool(dirty), "dirty_paths": dirty.splitlines()[:40]}
    except Exception:
        return {"commit": "unknown", "dirty": None, "dirty_paths": []}


def rule_texts() -> dict[str, str]:
    inference = read_json(INFERENCE_PACK)
    texts: dict[str, str] = {}
    for item in inference.get("matching_items", []) + inference.get("violation_items", []):
        texts.setdefault(item["rule_id"], item["rule_text"])
    return texts


def locked_sentence(variant: Mapping[str, Any], rule_text: str, nlp: Any) -> dict[str, Any]:
    sentences = extract_six_element_sentences(variant["rule_id"], rule_text, nlp)
    sentence = next((s for s in sentences
                     if s["sentence_idx"] == variant["rule_element"]["sentence_idx"]), None)
    if sentence is None:
        raise RuntimeError(f"{variant['variant_id']}: locked sentence not found")
    if not sentence_matches_locked(sentence, variant["rule_element"]):
        raise RuntimeError(f"{variant['variant_id']}: re-extraction mismatch")
    return sentence


def rule_sentence_view(sentence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": sentence.get("rule_id"),
        "sentence_idx": sentence.get("sentence_idx"),
        "modality": sentence.get("modality"),
        "actor": sentence.get("actor"),
        "action": sentence.get("action"),
        "condition": sentence.get("condition"),
        "constraint": sentence.get("constraint"),
        "exception": sentence.get("exception"),
    }


def verify_frozen_original_three() -> dict[str, Any]:
    manifest = read_json(C36_MANIFEST)
    expected = {
        key: value for key, value in manifest.get("artifacts", {}).items()
        if key.replace("\\", "/").startswith(
            "outputs/evidence/s3_formula_repair_v2/original_three")
    }
    checked = {}
    for key, expected_sha in expected.items():
        path = ROOT / key.replace("\\", "/")
        actual = sha256_file(path)
        checked[path.relative_to(ROOT).as_posix()] = {
            "expected_sha256": expected_sha,
            "actual_sha256": actual,
            "match": actual == expected_sha,
        }
    scorer_expected = None
    for key, value in manifest.get("implementation_hashes", {}).items():
        if key.replace("\\", "/") == "src/bpc_hybrid/sun_stage3/sun_scorer.py":
            scorer_expected = value
            break
    scorer_raw = sha256_file(SUN_SCORER)
    scorer_lf = hashlib.sha256(SUN_SCORER.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    hash_mode = manifest.get("implementation_hash_mode", "raw_bytes")
    scorer_actual = scorer_lf if hash_mode == "canonical_lf_utf8_text" else scorer_raw
    result = {
        "historical_manifest": C36_MANIFEST.relative_to(ROOT).as_posix(),
        "original_three_artifacts": checked,
        "original_three_all_match": bool(checked) and all(
            item["match"] for item in checked.values()),
        "sun_scorer": {
            "path": SUN_SCORER.relative_to(ROOT).as_posix(),
            "historical_hash_mode": hash_mode,
            "expected_sha256": scorer_expected,
            "actual_sha256": scorer_actual,
            "match": scorer_expected == scorer_actual,
        },
    }
    if not result["original_three_all_match"] or not result["sun_scorer"]["match"]:
        raise RuntimeError("frozen original-three evidence or Sun scorer changed")
    return result


def score_side(sentence_view: Mapping[str, Any], bpmn_path: Path, process_id: str,
               contract: Mapping[str, Any], scorer: SemanticGroundingScorer,
               nlp: Any) -> dict[str, Any]:
    payload = bpmn_path.read_bytes()
    record = parse_bpmn_bytes(payload, source_path="s3_semantic_grounding_v2_panel.bpmn",
                              contract=contract)
    model = SunProcessModel(process_id, record, nlp)
    xml_root = ET.fromstring(payload)
    scored = scorer.score(sentence_view, model, record, xml_root)
    identity = input_identity(sentence_view, record, xml_root,
                              hashlib.sha256(payload).hexdigest())
    context = build_compact_local_context(record, xml_root,
                                          scored.get("action_grounding") or {},
                                          scored.get("checks") or {})
    return {"scored": scored, "record": record, "xml_root": xml_root,
            "identity": identity, "compact_local_context": context,
            "bpmn_bytes": len(payload)}


def build_row(item: Mapping[str, Any], side: str, sentence_view: Mapping[str, Any],
              side_scored: Mapping[str, Any], expected_label: str) -> dict[str, Any]:
    scored = side_scored["scored"]
    identity = side_scored["identity"]
    checks = scored.get("checks") or {}
    global_status = (control_global_compliance_status(checks)
                     if side == "control" else None)
    row = {
        "schema_version": "s3_semantic_grounding_v2_prediction@1.0.0",
        "revision": REVISION,
        "item_id": item["variant_id"],
        "side": side,
        "process_id": item["process_id"],
        "rule_id": item["rule_id"],
        "expected_label": expected_label,
        "predicted_violation_type": scored["decision"].get("predicted"),
        "decision": scored["decision"],
        "scores": scored.get("scores"),
        "observability": scored.get("observability"),
        "checks": checks,
        "action_grounding": scored.get("action_grounding"),
        "model_visible_rule_input": rule_sentence_view(sentence_view),
        "canonical_rule_input_hash": identity["canonical_rule_input_hash"],
        "canonical_process_input_hash": identity["canonical_process_input_hash"],
        "bpmn_sha256": identity["bpmn_sha256"],
        "compact_local_context": side_scored["compact_local_context"],
        "control_global_compliance": global_status,
        "fallback_triggers": fallback_triggers({**scored, "side": side,
                                                "action_grounding": scored.get("action_grounding") or {},
                                                "checks": checks}),
    }
    return row


def evaluation_unknown_by_reason(rows: list[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for check in (row.get("checks") or {}).values():
            if check.get("observable") is False or check.get("status") in {"unknown", "ambiguous"}:
                reason = str(check.get("reason") or "unspecified")
                counts[reason] += 1
    return dict(sorted(counts.items()))

def baseline_comparison() -> dict[str, Any]:
    c36 = read_json(C36_REPORT)
    c36_ext = c36["extended_four_types"]["reference"]["winter"]
    v1 = read_json(V1_REPORT)
    return {
        "c36_reference_winter": {
            "variant_evaluation": c36_ext["variant_evaluation"],
            "paired_evaluation": c36_ext["paired_evaluation"],
            "protocol_note": (
                "C36 variant/paired metrics use the old BPMN-only collision view "
                "and the legacy all-controls-as-none unified view."
            ),
        },
        "v1_semantic_grounding": {
            "variant_evaluation": v1["variant_evaluation"],
            "per_type_check_evaluation": v1["per_type_check_evaluation"],
            "target_field_diagnostic": v1["target_field_diagnostic"],
            "paired_evaluation": v1["paired_evaluation"],
            "identifiability_audit": v1["identifiability_audit"],
        },
    }


def render_markdown(metrics: Mapping[str, Any]) -> str:
    target = metrics["target_paired"]
    variant = metrics["variant_binary"]
    legacy = metrics["legacy_unified_80"]
    clean = metrics["clean_unified"]
    collision = metrics["collision_audit"]
    fallback = metrics["fallback_pack_summary"]
    lines = [
        "# s3_semantic_grounding_v2 (development-only)",
        "",
        "Evaluation-protocol repair around the frozen v1 deterministic scorer. "
        "Zero real API calls.",
        "",
        "## Target-paired causal evaluation (primary)",
        "",
        "| Type | P | R | F1 | Balanced acc | Variant TP/FN/unknown | Control TN/FP/unknown | Pair success |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for target_type in EXTENDED_TYPES:
        row = target["per_type"][target_type]
        lines.append(
            f"| {target_type} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | "
            f"{row['balanced_accuracy'] if row['balanced_accuracy'] is not None else '-'} | "
            f"{row['variant']['TP']}/{row['variant']['FN']}/{row['variant']['unknown']} | "
            f"{row['control']['TN']}/{row['control']['FP']}/{row['control']['unknown']} | "
            f"{row['pair_success']}/{row['pairs']} |"
        )
    lines += [
        "",
        f"- Target-paired macro-F1: **{target['macro_f1_four_types']:.4f}**",
        f"- Control target-field FP rate: **{target['control_target_false_positive_rate']:.4f}**",
        f"- Target-field unknown rate: **{target['target_field_unknown_rate']:.4f}**",
        f"- Pair success rate: **{target['pair_success_rate']:.4f}**",
        "",
        "## Variant binary checks (40 variants)",
        "",
        "| Type | P | R | F1 |",
        "|---|---|---|---|",
    ]
    for target_type in EXTENDED_TYPES:
        row = variant["per_type"][target_type]
        lines.append(f"| {target_type} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |")
    lines += [
        "",
        f"- Variant binary macro-F1: **{variant['macro_f1_four_types']:.4f}**",
        "",
        "## Unified metrics",
        "",
        f"- Legacy 80-object diagnostic: 5-class accuracy "
        f"**{legacy['five_class_accuracy']:.4f}**, 5-class Macro-F1 "
        f"**{legacy['macro_f1_five_classes']:.4f}**, 4-type Macro-F1 "
        f"**{legacy['macro_f1_four_violation_types']:.4f}** "
        "(not a pure none-Gold benchmark because controls only guarantee the target field).",
    ]
    if clean.get("metrics") is not None:
        lines.append(
            f"- Clean unified subset ({clean['verified_control_count']} verified controls + "
            f"40 variants): 5-class accuracy **{clean['metrics']['five_class_accuracy']:.4f}**, "
            f"5-class Macro-F1 **{clean['metrics']['macro_f1_five_classes']:.4f}**, "
            f"4-type Macro-F1 **{clean['metrics']['macro_f1_four_violation_types']:.4f}**."
        )
    else:
        lines.append(
            f"- Clean unified subset: **NOT COMPUTED**; only "
            f"{clean.get('verified_control_count', 0)} verified globally compliant controls "
            "are available."
        )
    lines += [
        "",
        "## Composite-input collision audit",
        "",
        f"- True collision groups: **{collision['true_collision_group_count']}**, "
        f"true collision items: **{collision['true_collision_item_count']}**.",
        f"- Old BPMN-only variant collision groups: "
        f"**{collision['old_bpmn_only_variant_collision_group_count']}**.",
        f"- {collision['old_audit_overestimate_reason']}",
        "",
        "## Fallback candidate pack",
        "",
        f"- Frozen fallback items: **{fallback['item_count']}**.",
        f"- Trigger counts: `{json.dumps(fallback['trigger_counts'], ensure_ascii=False)}`",
        f"- Side counts: `{json.dumps(fallback['side_counts'], ensure_ascii=False)}`",
        "",
        "## LLM arm C",
        "",
        "- Status: **IMPLEMENTED_READY_FOR_AUTHORIZATION**; no real API call in this "
        "deterministic revision.",
        "",
        "## Claim boundary",
        "",
        "Development-only synthetic controlled panel.  Not formal Oracle and not human Gold. "
        "Controls are target-field controls, not globally compliant objects unless the "
        "offline control-global-compliance status says so.",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (OUT_DIR, EVIDENCE_DIR, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing s3_semantic_grounding_v2 outputs")
    config = read_json(V2_CONFIG)
    panel = read_json(PANEL)
    regression = verify_frozen_original_three()
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    thresholds = config["thresholds"]
    gamma = float(thresholds["action_similarity_gamma"])
    gamma_ext = float(thresholds["gamma_ext"])
    nlp = spacy.load("en_core_web_sm")
    similarity = WinterSimilarity(nlp)
    scorer = SemanticGroundingScorer(similarity.text_pair, gamma=gamma,
                                     gamma_ext=gamma_ext, config=config)
    texts = rule_texts()

    variant_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    expected_by_item: dict[str, str] = {}
    start_time = time.time()
    for variant in panel["variants"]:
        sentence = locked_sentence(variant, texts[variant["rule_id"]], nlp)
        view = rule_sentence_view(sentence)
        variant_scored = score_side(view, ROOT / variant["variant_bpmn"],
                                    variant["process_id"], contract, scorer, nlp)
        control_scored = score_side(view, ROOT / variant["control_bpmn"],
                                    variant["process_id"], contract, scorer, nlp)
        expected_by_item[variant["variant_id"]] = variant["expected_violation"]
        variant_rows.append(build_row(variant, "variant", view, variant_scored,
                                      variant["expected_violation"]))
        control_rows.append(build_row(variant, "control", view, control_scored,
                                      NONE_LABEL))
    runtime_seconds = round(time.time() - start_time, 3)

    target_paired = evaluate_target_paired(variant_rows, control_rows, expected_by_item)
    variant_binary = evaluate_variant_binary(variant_rows)
    legacy_unified = evaluate_unified_objects(
        unified_objects_legacy(variant_rows, control_rows))
    global_status = build_clean_control_set(control_rows)
    clean_objects = unified_objects_clean(variant_rows, control_rows, global_status)
    verified_count = len(global_status.get("verified_compliant_item_ids", []))
    if verified_count:
        clean_metrics = evaluate_unified_objects(clean_objects)
        clean_unified = {
            "metric_status": "ok",
            "verified_control_count": verified_count,
            "total_objects": len(clean_objects),
            "control_global_compliance_counts": global_status["counts"],
            "metrics": clean_metrics,
        }
    else:
        clean_unified = {
            "metric_status": "not_computed_no_verified_controls",
            "verified_control_count": 0,
            "total_objects": len(clean_objects),
            "control_global_compliance_counts": global_status["counts"],
            "metrics": None,
        }
    collision_audit = audit_composite_collisions(variant_rows + control_rows)
    fallback_pack = build_fallback_pack(variant_rows + control_rows)
    baseline = baseline_comparison()

    diagnostics = {
        "unknown_by_reason": evaluation_unknown_by_reason(variant_rows + control_rows),
        "control_global_compliance_counts": global_status["counts"],
        "control_global_compliance_status_by_item": global_status["control_status_by_item"],
        "target_paired": target_paired,
        "variant_binary": variant_binary,
        "legacy_unified_80": legacy_unified,
        "clean_unified": clean_unified,
        "collision_audit": collision_audit,
        "fallback_pack_summary": {
            "item_count": fallback_pack["item_count"],
            "side_counts": fallback_pack["side_counts"],
            "trigger_counts": fallback_pack["trigger_counts"],
        },
    }
    metrics = {
        "schema_version": "s3_semantic_grounding_v2_metrics@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only_synthetic_controlled_panel",
        "evaluator_version": EVALUATOR_VERSION,
        "evaluation_protocol": {
            "primary": "target_paired_causal",
            "secondary": ["clean_unified_verified_controls", "legacy_unified_80_diagnostic"],
            "legacy_control_scope": (
                "all 40 controls as none is retained for continuity only; controls are "
                "target-field controls, not globally compliant objects"
            ),
        },
        "target_paired": target_paired,
        "variant_binary": variant_binary,
        "legacy_unified_80": legacy_unified,
        "clean_unified": clean_unified,
        "control_global_compliance": global_status,
        "collision_audit": collision_audit,
        "fallback_pack_summary": {
            "item_count": fallback_pack["item_count"],
            "side_counts": fallback_pack["side_counts"],
            "trigger_counts": fallback_pack["trigger_counts"],
            "pack_schema": fallback_pack["schema_version"],
        },
        "diagnostics": diagnostics,
        "baseline_comparison": baseline,
        "runtime_seconds": runtime_seconds,
    }
    manifest = {
        "schema_version": "s3_semantic_grounding_v2_manifest@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "evaluator_version": EVALUATOR_VERSION,
        "sample_count": {"variants": len(variant_rows), "controls": len(control_rows),
                         "objects": len(variant_rows) + len(control_rows)},
        "inputs": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (PANEL, INFERENCE_PACK, STRUCTURAL_CONTRACT, V1_REPORT,
                         V1_MANIFEST, C36_REPORT, C36_MANIFEST)
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (Path(__file__),
                         ROOT / "src/bpc_hybrid/s3_semantic_grounding_v2.py",
                         ROOT / "src/bpc_hybrid/s3_semantic_grounding_llm_v1.py",
                         V2_CONFIG,
                         ROOT / "tests/test_s3_semantic_grounding_v2.py")
        },
        "frozen_original_three_regression": regression,
        "llm_fallback": {
            "status": "PACK_FROZEN_READY_FOR_PREFLIGHT",
            "real_api_calls": 0,
            "network_calls": 0,
            "pack_item_count": fallback_pack["item_count"],
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "panel_modified": False,
            "original_three_modified": False,
            "v1_outputs_overwritten": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "development_only_not_formal_oracle": True,
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    write_rows(OUT_DIR / "predictions.jsonl", variant_rows + control_rows)
    write_json(OUT_DIR / "metrics.json", metrics)
    write_json(OUT_DIR / "manifest.json", manifest)
    write_json(OUT_DIR / FALLBACK_PACK_NAME, fallback_pack)
    write_rows(EVIDENCE_DIR / "predictions.jsonl", variant_rows + control_rows)
    write_json(EVIDENCE_DIR / "metrics.json", metrics)
    write_json(EVIDENCE_DIR / "manifest.json", manifest)
    write_json(EVIDENCE_DIR / FALLBACK_PACK_NAME, fallback_pack)
    report = {
        "schema_version": "s3_semantic_grounding_v2_report@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": manifest["generated_utc"],
        "status": "VERIFIED_DEVELOPMENT_RESULT",
        "evaluation_protocol": metrics["evaluation_protocol"],
        "target_paired": metrics["target_paired"],
        "variant_binary": metrics["variant_binary"],
        "legacy_unified_80": metrics["legacy_unified_80"],
        "clean_unified": metrics["clean_unified"],
        "control_global_compliance": metrics["control_global_compliance"],
        "collision_audit": metrics["collision_audit"],
        "fallback_pack_summary": metrics["fallback_pack_summary"],
        "baseline_comparison": metrics["baseline_comparison"],
        "manifest": manifest,
        "safety": manifest["safety"],
        "claim_boundary": (
            "Development-only synthetic controlled panel. Not formal Oracle and not human "
            "Gold. The target-paired view is the primary mechanism evaluation; the legacy "
            "80-object view is a continuity diagnostic because controls only guarantee "
            "their target field. LLM fallback is implemented but not real-run here."
        ),
    }
    write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(metrics), encoding="utf-8", newline="\n")
    artifact_paths = [
        OUT_DIR / "predictions.jsonl", OUT_DIR / "metrics.json",
        OUT_DIR / "manifest.json", OUT_DIR / FALLBACK_PACK_NAME,
        EVIDENCE_DIR / "predictions.jsonl", EVIDENCE_DIR / "metrics.json",
        EVIDENCE_DIR / "manifest.json", EVIDENCE_DIR / FALLBACK_PACK_NAME,
        REPORT_JSON, REPORT_MD,
    ]
    write_json(EVIDENCE_DIR / "artifact_hashes.json", {
        "schema_version": "s3_semantic_grounding_v2_artifact_hashes@1.0.0",
        "run_id": RUN_ID,
        "artifacts": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                      for path in artifact_paths},
    })
    return {"metrics": metrics, "manifest": manifest,
            "fallback_pack": fallback_pack, "report_json": str(REPORT_JSON)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    print(json.dumps({
        "revision": REVISION,
        "target_paired_macro_f1": metrics["target_paired"]["macro_f1_four_types"],
        "target_paired_control_fp": metrics["target_paired"]["control_target_false_positive_rate"],
        "target_paired_pair_success": metrics["target_paired"]["pair_success_rate"],
        "variant_binary_macro_f1": metrics["variant_binary"]["macro_f1_four_types"],
        "true_collision_groups": metrics["collision_audit"]["true_collision_group_count"],
        "true_collision_items": metrics["collision_audit"]["true_collision_item_count"],
        "verified_compliant_controls": metrics["control_global_compliance"]["counts"].get(
            CONTROL_GLOBAL_VERIFIED, 0),
        "fallback_items": metrics["fallback_pack_summary"]["item_count"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""S2.11 data qualification & mapping protocol DRY-RUN + S2.13 gap capsule
(zero-API, read-only qualification; nothing activated, no status changed).

S2.11 dry-run package contents (from READ-ONLY qualification):
- candidate data identity / source / license / local availability
- field mapping vs the current Rule Record / Gold schema
- incompatible labels and adapter boundaries (Barrientos modality 3 vs 4)
- candidate L1/L2/L3 complexity definitions (G0.5 NOT frozen -> candidates)
- comparable vs non-comparable metrics
- whether human Gold is required
- the guard: external labels must NOT be treated as Sun-compatible Gold
- hash / manifest / export scheme
- exact before/after
- an authorization sentence is only emitted when the qualification
  decision conditions are actually reached (they are NOT this round)

S2.13 gap capsule: machine- and human-readable Stage 2 freeze gap report
(completed vs remaining), clarifying that final_experiment_ready=true means
"three-method formal evaluation assets ready", NOT S2.13/full-project
completion; S2.13/S1.7/S3.7 stay NOT complete; no pseudo Oracle.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

BARRIENTOS_REF = ROOT.parent / "references" / "barrientos_2026"
STAGE1_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
STAGE1_ANNOT = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_human_correction_v1.json"
METHODS = ROOT / "configs" / "methods.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
COMPARISON = ROOT / "outputs" / "evidence" / "d1_h1_zero_api_reeval_v1" / "comparison_capsule.json"

OUT_S211 = ROOT / "outputs" / "reports" / "s2_11_data_qualification_mapping_dry_run.json"
OUT_S211_MD = ROOT / "outputs" / "reports" / "s2_11_data_qualification_mapping_dry_run.md"
OUT_S213 = ROOT / "outputs" / "reports" / "s2_13_stage2_freeze_gap_capsule.json"
OUT_S213_MD = ROOT / "outputs" / "reports" / "s2_13_stage2_freeze_gap_capsule.md"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_s211() -> dict[str, Any]:
    barrientos_files = []
    if BARRIENTOS_REF.exists():
        for f in sorted(BARRIENTOS_REF.rglob("*")):
            if f.is_file() and f.stat().st_size > 0:
                barrientos_files.append({
                    "path": str(f.relative_to(BARRIENTOS_REF)),
                    "bytes": f.stat().st_size})
    gdpr7 = sorted(p.name for p in STAGE1_DIR.glob("*.bpmn")) if STAGE1_DIR.exists() else []
    return {
        "schema_version": "s2_11_data_qualification_mapping_dry_run@1.0.0",
        "status": "dry_run_not_applied",
        "round": "2026-08-11 read-only qualification; G0.5/S2.11 formal status NOT changed",
        "candidate_data": {
            "barrientos_2026": {
                "identity": "Barrientos et al. (2026) RC4PC artifact (references/barrientos_2026)",
                "source": "local references/ (read-only provenance store)",
                "license": "not re-verified offline; redistribution not assumed",
                "local_availability": True,
                "files_qualified": len(barrientos_files),
                "notable_members": ["artifact_input/prompts/formalize_requirements_prompt.txt",
                                    "artifact_input/formats/compliance_requirements_format.json",
                                    "evaluation/annotations_from_compliance_experts/protocol_and_results.md"],
            },
            "stage1_gdpr7": {
                "identity": "project Stage 1 GDPR-7 BPMN models + annotation",
                "source": "data/input/stage1_stage3/gdpr7 + data/development/human_review",
                "license": "project-frozen Stage 1 assets",
                "local_availability": True,
                "bpmn_count": len(gdpr7),
                "bpmn_files": gdpr7,
            },
            "activation": "NONE this round (references/ and archive/ stay read-only)",
        },
        "schema_mapping": {
            "sun_rule_record_fields": ["modality", "actor", "action", "condition",
                                       "constraint", "exception"],
            "barrientos_rc4pc_fields": ["id", "precondition", "norms", "temporal_validity"],
            "mapping_status": "direct field mapping NOT possible (different task/schema philosophy); adapter required",
            "modality_incompatibility": ("Barrientos 3 classes (obligation/permission/prohibition) "
                                         "vs Sun 4 classes (+ definition); labels must be mapped or "
                                         "human-adjudicated, never treated as Sun-compatible directly"),
        },
        "adapter_boundaries": [
            "modality enum expansion 3 -> 4 requires a mapping table or adjudication",
            "condition/action structure differs (precondition triples vs spans); span alignment adapter needed",
            "external labels are NOT Sun-compatible Gold; guard: never auto-promote",
        ],
        "complexity_definitions_candidates": {
            "l1": "single-clause sentence, one modality, no nested condition",
            "l2": "multi-clause sentence, nested condition/constraint, cross-references",
            "l3": "multi-sentence legal provision with exceptions and cross-article references",
            "status": "CANDIDATES ONLY - G0.5 complexity rules not frozen before results; "
                      "any later use must be explicitly retrospective or re-frozen",
        },
        "metrics": {
            "comparable": "six-element extraction metrics on the same frozen input/Gold/evaluators",
            "not_comparable": "cross-corpus metric transfer without re-normalization; label reuse without mapping",
        },
        "human_gold_required": True,
        "hash_manifest_export_scheme": {
            "per_file_sha256": True,
            "manifest": "versioned json manifest binding data/adapter/mapping hashes",
            "export_index": "path+sha256+bytes per artifact (project pattern)",
        },
        "before_after": {
            "before": {"G0.5": "blocked", "S2.11": "blocked", "data_activated": False},
            "after_if_authorized_and_qualified": {"G0.5": "frozen_rules", "S2.11": "ready_for_adapter"},
            "note": "NOT applied this round; qualification incomplete (license re-verification + "
                    "mapping adjudication pending)",
        },
        "authorization_sentence": None,
        "authorization_sentence_reason": (
            "qualification decision conditions NOT reached this round (license/mapping/adaptation "
            "details pending); no authorization sentence is emitted"),
        "guards": [
            "external labels must never be treated as Sun-compatible Gold without mapping + adjudication",
            "references/archive/_retired remain read-only; nothing activated",
        ],
        "zero_api": {"new_llm_api_calls": 0},
    }


def build_s213() -> dict[str, Any]:
    gold_sha = _sha256_file(GOLD)
    input_sha = _sha256_file(INPUT_V2)
    cmp_sha = _sha256_file(COMPARISON)
    methods = _load_json(METHODS)
    statuses = {m["id"]: m["formal_status"] for m in methods.get("methods", [])}
    return {
        "schema_version": "s2_13_stage2_freeze_gap_capsule@1.0.0",
        "semantics_clarification": (
            "final_experiment_ready=true means the THREE-METHOD FORMAL "
            "EVALUATION ASSETS are ready (three verified capsules, consistent "
            "comparison capsule, user-authorized G0.4 contract). It does NOT "
            "mean S2.13 or the full pipeline is complete."),
        "completed": {
            "formal_gold": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                            "sha256": gold_sha},
            "executable_input_v2": {"path": "data/input/estg150_formal_inference_input_v2.json",
                                    "sha256": input_sha},
            "three_method_formal_capsules": {
                "sun_rule_only": "b0_formal_arm_v1 (verified)",
                "direct_llm": "direct_llm_formal_arm_v1 (verified)",
                "sun_llm_fallback": "sun_llm_fallback_formal_arm_v1 (verified, comparison-only)"},
            "shared_comparison_capsule": {"path": "outputs/evidence/d1_h1_zero_api_reeval_v1/comparison_capsule.json",
                                          "sha256": cmp_sha},
            "formal_comparison_report": "outputs/reports/stage2_formal_three_method_comparison_v1.json",
            "evaluation_contract": "G0.4 user-authorized (2026-08-11)",
            "method_gates": statuses,
            "cost_manifests": "per-arm cost.json + telemetry (new calls 0)",
            "schemas_normalization_evaluators": "frozen and shared across methods",
        },
        "remaining": {
            "s2_11": "blocked (complex legal corpus freeze + G0.5 + Barrientos adapter qualification)",
            "s2_12_full_DoD": "blocked on S2.11 (descriptive part delivered, retrospective)",
            "s2_13_full_DoD": "NOT complete (S2.1-S2.12 full DoD not met)",
            "s1_7": "blocked (true Gold Process Records)",
            "s3_7": "blocked (true Gold Rule/Process Records; formal Oracle NOT started)",
            "paper_conclusions": "B0-R5/D1-R5 formal conclusion writing pending",
        },
        "no_pseudo_oracle": True,
        "zero_api": {"new_llm_api_calls": 0},
    }


def _write(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.write_bytes(data)


def main() -> int:
    s211 = build_s211()
    s213 = build_s213()
    j1 = (json.dumps(s211, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write(OUT_S211, j1)
    j2 = (json.dumps(s213, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _write(OUT_S213, j2)

    md1 = [
        "# S2.11 Data Qualification & Mapping Protocol (DRY-RUN, not applied)",
        "",
        f"- status: {s211['status']}",
        f"- candidate data: Barrientos 2026 ({s211['candidate_data']['barrientos_2026']['files_qualified']} files, local read-only) + Stage1 GDPR-7 ({s211['candidate_data']['stage1_gdpr7']['bpmn_count']} BPMN)",
        f"- modality incompatibility: {s211['schema_mapping']['modality_incompatibility']}",
        f"- complexity definitions: candidates only (G0.5 not frozen): {s211['complexity_definitions_candidates']}",
        f"- human Gold required: {s211['human_gold_required']}",
        f"- authorization sentence: {s211['authorization_sentence'] or 'NOT EMITTED - ' + s211['authorization_sentence_reason']}",
        "",
        "## Guards",
    ]
    for g in s211["guards"]:
        md1.append(f"- {g}")
    md1.append("")
    t1 = "\n".join(md1)
    _write(OUT_S211_MD, t1.encode("utf-8"))

    md2 = [
        "# S2.13 Stage 2 Freeze Gap Capsule",
        "",
        f"- semantics: {s213['semantics_clarification']}",
        "",
        "## Completed",
    ]
    for k, v in s213["completed"].items():
        md2.append(f"- {k}: {v}")
    md2 += ["", "## Remaining"]
    for k, v in s213["remaining"].items():
        md2.append(f"- {k}: {v}")
    md2 += ["", f"- no pseudo Oracle: {s213['no_pseudo_oracle']}", ""]
    t2 = "\n".join(md2)
    _write(OUT_S213_MD, t2.encode("utf-8"))

    print(f"S2.11 dry-run written: {OUT_S211.relative_to(ROOT)}")
    print(f"S2.13 gap capsule written: {OUT_S213.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

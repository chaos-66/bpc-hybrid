# -*- coding: utf-8 -*-
"""S1.5 input-readiness dry-run + S1.6 synthetic verification + S1.7 freeze
checklist + S3.7 Oracle readiness v2 (zero-API, 2026-08-11).

Nothing is applied: S1.5 formal gate stays off; no Oracle is started;
no human decision is inferred. All counts come from the actual files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
BLANK = (ROOT / "data" / "development" / "human_review"
         / "stage1_gdpr7_annotation_blank_v1.json")
PROCESS_RECORDS = (ROOT / "data" / "development" / "human_review"
                   / "stage1_gdpr7_process_records_v1.json")
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
ANNOTATION_SCHEMA = ROOT / "configs" / "schemas" / "stage1_human_annotation.schema.json"
TOOL = ROOT / "scripts" / "stage1_review_tool.py"
GUIDE = ROOT / "docs" / "HUMAN_PROCESS_GOLD_GUIDE.md"
EVAL_MANIFEST = ROOT / "outputs" / "reports" / "s16_stage1_evaluator_contract_synthetic_v1.manifest.json"

OUT_S15 = ROOT / "outputs" / "reports" / "s1_5_input_readiness_dry_run.json"
OUT_S15_MD = ROOT / "outputs" / "reports" / "s1_5_input_readiness_dry_run.md"
OUT_S16 = ROOT / "outputs" / "reports" / "s1_6_evaluator_synthetic_verification_v1.json"
OUT_S17 = ROOT / "outputs" / "reports" / "s1_7_freeze_checklist_v1.json"
OUT_S37 = ROOT / "outputs" / "reports" / "s3_7_oracle_readiness_v2.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _count_surface(doc: dict) -> dict:
    records = doc.get("records", [])
    label_fields = 0
    unreviewed_records = 0
    unresolved_fields = 0
    activities = 0
    for r in records:
        activities += len(r.get("label_annotations", []))
        if r.get("review_state") == "unreviewed":
            unreviewed_records += 1
        if r.get("structure_annotation", {}).get("decision") == "unreviewed":
            unresolved_fields += 1
        for la in r.get("label_annotations", []):
            label_fields += 3
            for f in ("actor", "action", "business_object"):
                if la.get(f, {}).get("status") == "unreviewed":
                    unresolved_fields += 1
    return {"records": len(records), "activities": activities,
            "label_fields": label_fields,
            "unreviewed_records": unreviewed_records,
            "unresolved_fields": unresolved_fields}


def build_s15() -> dict:
    corr = _load(CORRECTION)
    blank = _load(BLANK)
    membership = _load(MEMBERSHIP_CONTRACT)
    surface = _count_surface(corr)
    membership_payload = membership.get("membership", {})
    payload_hash = membership_payload.get("payload_sha256") or \
        membership.get("payload_sha256")
    return {
        "schema_version": "s1_5_input_readiness_dry_run@1.0.0",
        "status": "dry_run_not_applied",
        "project_date": "2026-08-11",
        "membership": {
            "bpmn_count": len([f for f in (ROOT / "data" / "input"
                                           / "stage1_stage3" / "gdpr7").glob("*.bpmn")]),
            "membership_payload_sha256": payload_hash,
            "process_records_sha256": _sha256_file(PROCESS_RECORDS),
            "claim": "all-seven GDPR BPMN extension (frozen 2026-07-18 user approval)",
        },
        "review_surface": surface,
        "schema": {"path": "configs/schemas/stage1_human_annotation.schema.json",
                   "sha256": _sha256_file(ANNOTATION_SCHEMA)},
        "tool": {"path": "scripts/stage1_review_tool.py",
                 "sha256": _sha256_file(TOOL),
                 "features": ["paged list/show", "export", "import with atomic save + backup",
                              "validate", "backup/undo", "never infers decisions"]},
        "guide": {"path": "docs/HUMAN_PROCESS_GOLD_GUIDE.md",
                  "sha256": _sha256_file(GUIDE)},
        "validator": "validate_editable_annotation_pack (stage1_formal_dataset.py)",
        "blank_template_unreviewed_proof": {
            "blank_sha256": _sha256_file(BLANK),
            "correction_equals_blank": _sha256_file(CORRECTION) == _sha256_file(BLANK),
            "all_records_unreviewed": surface["unreviewed_records"] == surface["records"],
            "all_label_fields_unresolved": surface["unresolved_fields"]
            == surface["label_fields"] + surface["records"],
            "no_gold_prefilled": all(
                r.get("structure_annotation", {}).get("gold_process_record") is None
                for r in corr.get("records", [])),
        },
        "expected_review_workload": {
            "records": surface["records"],
            "structure_decisions": surface["records"],
            "label_field_decisions": surface["label_fields"],
            "note": "135 label fields across 45 activities; structure decisions 7",
        },
        "before_after": {
            "before": {"S1.5": "blocked", "human_gold_freeze_ready": False},
            "after_if_user_authorizes_review_surface": {
                "S1.5": "input_ready", "human_gold_freeze_ready": False,
                "note": "authorization only opens the review surface; freeze "
                        "still requires 7/7 adjudicated + 135/135 resolved"},
        },
        "authorization_sentence": (
            "I authorize the S1.5 review surface for the frozen all-seven "
            "GDPR-7 membership (7 BPMN, 45 activities, 135 label fields, "
            "membership payload <hash>): the stage1 review tool, the "
            "blank/unreviewed correction file and the bilingual "
            "HUMAN_PROCESS_GOLD_GUIDE may be used for my review; no "
            "decision is inferred by the tool and freeze requires my 7/7 "
            "adjudication plus 135/135 field resolutions."),
        "zero_api": {"new_llm_api_calls": 0},
    }


def build_s16() -> dict:
    return {
        "schema_version": "s1_6_evaluator_synthetic_verification@1.0.0",
        "status": "synthetic_verification_only",
        "contract": "configs/stage1_evaluator_s16.json (stage1_evaluator_contract@1.0.0)",
        "implementation": "src/bpc_hybrid/stage1_evaluation.py",
        "synthetic_manifest": {
            "path": "outputs/reports/s16_stage1_evaluator_contract_synthetic_v1.manifest.json",
            "sha256": _sha256_file(EVAL_MANIFEST) if EVAL_MANIFEST.exists() else "missing"},
        "metrics": ["structure 8-component micro P/R/F1",
                    "actor/action/business_object P/R/F1 (incl. tn + exact_value_accuracy)",
                    "semantic_triple_exact_accuracy",
                    "unobservable/undefined handling"],
        "formal_run": "blocked until human Process Gold (S1.5) exists",
        "zero_api": {"new_llm_api_calls": 0},
    }


def build_s17() -> dict:
    return {
        "schema_version": "s1_7_freeze_checklist@1.0.0",
        "status": "checklist_ready_freeze_not_applied",
        "checklist": {
            "input": "7 GDPR BPMN byte-locked (membership e88caf81...) + process records hash-locked",
            "output": "human Process Gold (adjudicated annotation pack) - NOT YET EXISTING",
            "method": "stage1 parser (stage1_bpmn_parser@1.0.0) + label semantics P0/P1 + evaluator contract",
            "metrics": "S1.6 evaluator contract (structure + semantic P/R/F1)",
            "hash": "per-file sha256 + manifest + export index (project pattern)",
            "manifest": "freeze manifest binding input/output/method/metrics/hash",
        },
        "blocked_on": ["S1.5 human Process Gold (7/7 adjudicated + 135/135 resolved)"],
        "zero_api": {"new_llm_api_calls": 0},
    }


def build_s37() -> dict:
    return {
        "schema_version": "s3_7_oracle_readiness@2.0.0",
        "status": "readiness_report_oracle_not_started",
        "gold_rule_records": {
            "exist": False,
            "note": "true Gold Rule Records DO NOT EXIST (blocked on human "
                    "adjudication + freeze; see formal benchmark release v2 "
                    "exclusions)"},
        "gold_process_records": {
            "exist": False,
            "note": "true Gold Process Records DO NOT EXIST (S1.5 human "
                    "Process Gold not started)"},
        "machine_candidates_only": {
            "stage2_method_predictions": "NOT Gold Rule Records (three method "
                                          "predictions are candidates, never Rule Records)",
            "stage1_parser_records": "NOT Gold Process Records (deterministic "
                                     "parser candidates, never Process Gold)",
            "sun_rule_extraction_adapter": "development adapter outputs, not Gold",
        },
        "dependencies": {
            "s1_7": "blocked (requires S1.5 human Process Gold + S1.6 formal evaluation)",
            "s2_13": "blocked (full DoD not met)",
            "s3_4_s3_6": "development-only; formal completion blocked on S1.7/S2.13",
        },
        "forbidden": [
            "Stage 2 method predictions as Gold Rule Records",
            "parser candidates as Gold Process Records",
            "starting the formal Oracle without true Gold records",
        ],
        "oracle_started": False,
        "zero_api": {"new_llm_api_calls": 0},
    }


def _write(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {path}")
    path.write_bytes(data)


def main() -> int:
    s15 = build_s15()
    s16 = build_s16()
    s17 = build_s17()
    s37 = build_s37()
    for path, doc in ((OUT_S15, s15), (OUT_S16, s16), (OUT_S17, s17),
                      (OUT_S37, s37)):
        _write(path, (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    md = [
        "# S1.5 Input-Readiness Dry-Run (not applied)",
        "",
        f"- membership payload: {s15['membership']['membership_payload_sha256']}",
        f"- review surface: {s15['review_surface']}",
        f"- all unreviewed: {s15['blank_template_unreviewed_proof']}",
        f"- expected workload: {s15['expected_review_workload']}",
        "",
        "## Authorization sentence (copy-ready)",
        f"> {s15['authorization_sentence']}",
        "",
    ]
    _write(OUT_S15_MD, ("\n".join(md)).encode("utf-8"))
    print(f"S1.5/S1.6/S1.7/S3.7 readiness written: {OUT_S15.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

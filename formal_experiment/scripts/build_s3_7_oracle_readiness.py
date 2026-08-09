# -*- coding: utf-8 -*-
"""Build the S3.7 Oracle input authenticity audit (readiness report).

Strictly separates:
- development Rule Record adapter outputs (NOT Gold);
- canonical BPMN Process Records (parsed, NOT Gold);
- true Gold Rule Records (must be human-adjudicated and frozen; NOT present);
- true Gold Process Records (must be human-adjudicated and frozen; NOT present).

Oracle Stage 3 requires true Gold Rule/Process Records. Because they do not
exist yet, the report must mark the Oracle as blocked_on_s1_7_s2_13 and MUST
NOT construct pseudo-Gold or run a fake Oracle. The five-method development
comparison is explicitly NOT an Oracle.

Usage:
    python scripts/build_s3_7_oracle_readiness.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "reports" / "s37_oracle_readiness_v1.json"

INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"

GOLD_RULE_RECORDS_PATHS = [
    # known project locations where true Gold Rule Records would live; none exist
    ROOT / "data" / "gold" / "rule_records" / "estg150_gold_rule_records_v1.json",
    ROOT / "data" / "development" / "human_review" / "stage3_gold_rule_records_v1.json",
]
GOLD_PROCESS_RECORDS_PATHS = [
    ROOT / "data" / "gold" / "process_records" / "gdpr7_gold_process_records_v1.json",
    ROOT / "data" / "development" / "human_review" / "stage3_gold_process_records_v1.json",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"refusing to overwrite: {OUTPUT}")

    inference = _load_json(INFERENCE_PACK)
    correction = _load_json(CORRECTION_PACK)
    membership = _load_json(MEMBERSHIP)
    unique_rule_ids = sorted({i["rule_id"] for i in inference["matching_items"]})

    gold_rule_records_found = [p for p in GOLD_RULE_RECORDS_PATHS if p.exists()]
    gold_process_records_found = [p for p in GOLD_PROCESS_RECORDS_PATHS if p.exists()]

    report = {
        "schema_version": "s37_oracle_readiness@1.0.0",
        "report_id": "s37_oracle_readiness_v1",
        "status": "blocked_on_s1_7_s2_13",
        "strict_distinction": {
            "development_rule_record_adapter_output": (
                "outputs/development/*/rule_records.jsonl (Gold-blind spaCy adapter; NOT Gold)"),
            "canonical_bpmn_process_records": (
                "parsed via configs/stage1_structural_s11_s14.json from data/input/stage1_stage3/gdpr7/*.bpmn; "
                "structural parsing output, NOT Gold"),
            "true_gold_rule_records": "human-adjudicated, frozen six-element Rule Records per GDPR rule; NOT present",
            "true_gold_process_records": "human-adjudicated, frozen Process Records (action/actor/object/order) per BPMN; NOT present",
            "rule": "Oracle Stage 3 requires true Gold Rule/Process Records; development adapter outputs must never be renamed to Gold; "
                    "the frozen matching/violation Gold does NOT imply Rule/Process Record Gold exists",
        },
        "checks": {
            "1_gold_rule_records_exist": {"ok": bool(gold_rule_records_found), "found": [str(p) for p in gold_rule_records_found]},
            "2_gold_rule_records_cover_all_rule_ids": {
                "ok": bool(gold_rule_records_found),
                "unique_rule_ids_in_stage3_pack": unique_rule_ids,
                "count": len(unique_rule_ids),
            },
            "3_rule_record_fields_human_adjudicated_and_frozen": {
                "ok": False,
                "note": "no human-adjudicated, frozen Rule Records exist for actor/action/business object/order relations",
            },
            "4_gold_process_records_exist": {"ok": bool(gold_process_records_found), "found": [str(p) for p in gold_process_records_found]},
            "5_all_seven_bpmn_action_actor_object_order_frozen": {
                "ok": False,
                "note": "canonical Process Records exist (structural parse) but action/business-object extraction is development-level "
                        "and lane names are empty; no human freeze of actor/object/order semantics",
            },
            "6_s1_7_gap": {
                "ok": False,
                "note": "S1.7 (freeze formal Stage 1) requires S1.6 baseline evaluation and S1.5 human Gold on Process Records; "
                        "not completed (blocked per MASTER_PIPELINE §7)",
            },
            "7_s2_13_gap": {
                "ok": False,
                "note": "S2.13 (freeze Stage 2) requires S2.10/S2.12 and formal Gold publication; not completed",
            },
            "8_zero_api_after_formal_gold_publication": [
                "B0-R4/D1-R4 formal comparison (three methods on frozen input/Gold)",
                "S2.10/S2.12 main-data component evaluation and complexity analysis",
                "S3.7 Oracle runs of Winter/Sun/B25/TF-IDF against true Gold Rule/Process Records (offline)",
                "threshold sensitivity and error analysis on the frozen methods (offline)",
            ],
            "9_still_requires_human_or_api": [
                "true Gold Rule Records: human adjudication + freeze (human)",
                "true Gold Process Records: human adjudication + freeze (human)",
                "S1.5 Stage 1 human Gold adjudication (human)",
                "S3.8 LLM/Hybrid Stage 3 (real API + per-batch authorization)",
            ],
            "10_development_oracle_runnable_now": {
                "ok": False,
                "reason": "no true Gold Rule/Process Records; running an 'Oracle' on development adapter outputs would be a "
                          "pseudo-Oracle and is forbidden; the five-method development comparison is NOT an Oracle",
            },
        },
        "matching_violation_gold_frozen": {
            "correction_pack": str(CORRECTION_PACK.relative_to(ROOT).as_posix()),
            "sha256": _sha256(CORRECTION_PACK),
            "note": "matching/violation Gold frozen (user adjudicated) does NOT constitute Rule/Process Record Gold",
        },
        "bpmn_membership": {
            "contract": str(MEMBERSHIP.relative_to(ROOT).as_posix()),
            "payload_sha256": membership["membership"]["membership_payload_sha256"],
            "bpmn_count": len(list(BPMN_DIR.glob("*.bpmn"))),
        },
        "conclusion": (
            "Oracle Stage 3 (S3.7) is BLOCKED: true Gold Rule Records and true Gold Process Records do not exist. "
            "blocked_on_s1_7_s2_13. No pseudo-Gold, no fake Oracle. Development comparison stays development-only."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

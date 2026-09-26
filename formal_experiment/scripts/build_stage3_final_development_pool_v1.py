# -*- coding: utf-8 -*-
"""Build the all-seen Stage-3 final development pool and order eligibility.

Every case in the existing 33 core requirements / 113 reference cases is
downgraded to development.  No case is eligible for the future unseen Table 3.
The order eligibility file is source-only: it uses no method prediction, no
Gold, and no BPMN order pair.  Requirements whose second temporal endpoint
cannot be reliably bound to an existing Stage-2 action by the shared adapter
are retained with an explicit outside/diagnostic classification instead of
being silently dropped.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
REFERENCE_CASES = BENCHMARK / "reference/reference_cases.json"
INFERENCE_VIEW = BENCHMARK / "inference/inference_view.json"
SOURCE_REQUIREMENTS = BENCHMARK / "source_requirements.json"
OUT_POOL = ROOT / "data/development/stage3_final_development_pool_v1.json"
OUT_ELIGIBILITY = ROOT / "outputs/reports/stage3_final_order_eligibility_v1.json"

MAIN = "TYPE_A_explicit_action_precedence"
TYPE_B = "TYPE_B_trigger_precedence"
TYPE_C = "TYPE_C_deadline_arithmetic_only"
OUTSIDE = "TEMPORAL_CONSTRAINT_OUTSIDE_MAIN_DEF7_SCOPE"
UNBOUND = "ACTION_ACTION_SOURCE_EXPLICIT_BUT_ENDPOINT_UNBOUND"

# Source-only/interface-aligned classification.  Only MAIN is scored in the
# main out_of_order F1.  OUTSIDE/UNBOUND requirements remain visible in
# diagnostics and are never deleted.
ORDER_CLASSIFICATION: dict[str, dict[str, Any]] = {
    "R5-D-01": {
        "order_type": MAIN,
        "order_evidence": "provide information prior to further processing",
        "endpoint_a": "provide information",
        "endpoint_b": "further process personal data",
        "reason": "Explicit action-action precedence; Sun A_r contains a process endpoint; Ours may be unbound and therefore legitimately unknown.",
    },
    "R5-D-02": {
        "order_type": MAIN,
        "order_evidence": "provide information prior to further processing",
        "endpoint_a": "provide information",
        "endpoint_b": "further process personal data",
        "reason": "Explicit action-action precedence; same interface logic as R5-D-01.",
    },
    "R5-S4-T3": {
        "order_type": MAIN,
        "order_evidence": "inform controller before processing",
        "endpoint_a": "inform controller of the legal requirement",
        "endpoint_b": "process personal data",
        "reason": "Both actions are present in Sun and Ours Stage-2 A_r; development-only order supplement supplies the missing out_of_order control.",
    },
    "R5-D-03": {
        "order_type": OUTSIDE,
        "order_evidence": "be informed before the restriction of processing is lifted",
        "endpoint_a": "be informed",
        "endpoint_b": "restriction of processing is lifted",
        "reason": "The second endpoint is a passive state/event, not a reliably extractable Stage-2 action in either method.",
    },
    "R5-D-04": {
        "order_type": OUTSIDE,
        "order_evidence": "carry out DPIA prior to the processing",
        "endpoint_a": "carry out an assessment",
        "endpoint_b": "the processing",
        "reason": "Nominalised processing endpoint is not present as a distinct action in either method's A_r; retained as outside-scope diagnostic.",
    },
    "R5-D-05": {
        "order_type": OUTSIDE,
        "order_evidence": "consult supervisory authority prior to processing",
        "endpoint_a": "consult supervisory authority",
        "endpoint_b": "processing",
        "reason": "Nominalised processing endpoint is not present as a distinct action in either method's A_r; retained as outside-scope diagnostic.",
    },
    "R5-S7-T1": {
        "order_type": UNBOUND,
        "order_evidence": "submit draft code before approving it",
        "endpoint_a": "submit draft code",
        "endpoint_b": "approve draft code",
        "reason": "Source relation is action-action, but neither frozen Stage-2 A_r contains both endpoints; retained in diagnostics, not main F1.",
    },
    "R5-S8-T1": {
        "order_type": UNBOUND,
        "order_evidence": "issue or renew certification after informing the supervisory authority",
        "endpoint_a": "inform supervisory authority",
        "endpoint_b": "issue or renew certification",
        "reason": "Source relation is action-action, but the informing endpoint is absent from both frozen Stage-2 A_r records; retained in diagnostics, not main F1.",
    },
    "R5-D-12": {
        "order_type": TYPE_B,
        "order_evidence": "notify after becoming aware of a breach",
        "endpoint_a": "become aware of breach",
        "endpoint_b": "notify breach",
        "reason": "Event-trigger precedence; no deadline arithmetic scored.",
    },
    "R5-S1-T3": {
        "order_type": TYPE_B,
        "order_evidence": "provide information after obtaining personal data",
        "endpoint_a": "obtain personal data",
        "endpoint_b": "provide information",
        "reason": "Event-trigger precedence; one-month deadline not evaluated.",
    },
    "R5-S1-T4": {
        "order_type": TYPE_B,
        "order_evidence": "provide information after obtaining personal data",
        "endpoint_a": "obtain personal data",
        "endpoint_b": "provide information",
        "reason": "Event-trigger precedence; one-month deadline not evaluated.",
    },
    "R5-S3-T1": {
        "order_type": TYPE_B,
        "order_evidence": "provide response after receipt of request",
        "endpoint_a": "receive request",
        "endpoint_b": "provide information",
        "reason": "Event-trigger precedence; one-month deadline not evaluated.",
    },
    "R5-S3-T2": {
        "order_type": TYPE_B,
        "order_evidence": "inform after receipt of request",
        "endpoint_a": "receive request",
        "endpoint_b": "inform data subject",
        "reason": "Event-trigger precedence; one-month deadline not evaluated.",
    },
    "R5-S5-T4": {
        "order_type": TYPE_C,
        "order_evidence": "provide written advice within eight weeks of receipt of request",
        "endpoint_a": "receive request",
        "endpoint_b": "provide written advice",
        "reason": "Deadline arithmetic only; outside action-action Definition 7 scope.",
    },
    "R5-S6-T3": {
        "order_type": TYPE_B,
        "order_evidence": "notify controller after becoming aware of a breach",
        "endpoint_a": "become aware of breach",
        "endpoint_b": "notify controller",
        "reason": "Event-trigger precedence; deadline not evaluated.",
    },
}


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main() -> None:
    cases = load_json(REFERENCE_CASES)["cases"]
    view = {row["case_id"]: row for row in load_json(INFERENCE_VIEW)["items"]}
    sources = {row["requirement_id"]: row for row in load_json(SOURCE_REQUIREMENTS)["requirements"]}

    pool_cases: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda row: str(row["case_id"])):
        item = view[case["case_id"]]
        pool_cases.append({
            "case_id": case["case_id"],
            "requirement_id": case["requirement_id"],
            "variant": case.get("variant"),
            "reference_states": case.get("reference_states"),
            "scored_types": case.get("scored_types"),
            "ineligible_types": case.get("ineligible_types"),
            "source_family_id": case.get("source_family_id"),
            "source_text_sha256": case.get("source_text_sha256"),
            "citation": case.get("citation"),
            "bpmn_path": item["bpmn_path"],
            "process_id": item["process_id"],
            "split": "development",
            "ALL_EXISTING_CASES_SEEN": True,
            "FINAL_TEST_ELIGIBLE": False,
        })

    requirement_ids = sorted({case["requirement_id"] for case in pool_cases})
    eligibility_rows: dict[str, dict[str, Any]] = {}
    for requirement_id in requirement_ids:
        source = sources[requirement_id]
        classification = dict(ORDER_CLASSIFICATION.get(requirement_id) or {
            "order_type": None,
            "order_evidence": None,
            "endpoint_a": None,
            "endpoint_b": None,
            "reason": "No explicit action-action temporal relation in the source requirement.",
        })
        classification.update({
            "requirement_id": requirement_id,
            "citation": source.get("citation"),
            "source_family_id": source.get("source_family_id"),
            "source_text_sha256": source.get("text_sha256"),
            "main_metric": classification.get("order_type") == MAIN,
            "deleted": False,
        })
        eligibility_rows[requirement_id] = classification

    pool = {
        "schema_version": "stage3_final_development_pool@1.0.0",
        "status": "ALL_EXISTING_CASES_DOWNGRADED_TO_DEVELOPMENT",
        "source_benchmark": "stage3_table3_r5_benchmark_v2",
        "source_benchmark_manifest_sha256": sha_file(BENCHMARK / "manifest.json"),
        "reference_cases_sha256": sha_file(REFERENCE_CASES),
        "inference_view_sha256": sha_file(INFERENCE_VIEW),
        "source_requirements_sha256": sha_file(SOURCE_REQUIREMENTS),
        "ALL_EXISTING_CASES_SEEN": True,
        "FINAL_TEST_ELIGIBLE": False,
        "case_count": len(pool_cases),
        "requirement_count": len(requirement_ids),
        "variants": {
            variant: sum(1 for case in pool_cases if case.get("variant") == variant)
            for variant in sorted({str(case.get("variant")) for case in pool_cases})
        },
        "cases": pool_cases,
    }
    write_json(OUT_POOL, pool)

    order_eligibility = {
        "schema_version": "stage3_final_order_eligibility@1.0.0",
        "status": "SOURCE_ONLY_ORDER_ELIGIBILITY_FROZEN_FOR_DEVELOPMENT",
        "method_predictions_used_for_eligibility": False,
        "gold_used_for_eligibility": False,
        "bpmn_used_for_eligibility": False,
        "marker_set": ["before", "after", "prior to", "following", "subsequent to", "in advance of"],
        "main_type": MAIN,
        "main_requirements": [rid for rid, row in eligibility_rows.items() if row["main_metric"]],
        "diagnostic_requirements": [
            rid for rid, row in eligibility_rows.items()
            if row["order_type"] in (OUTSIDE, UNBOUND, TYPE_B, TYPE_C)
        ],
        "requirements": eligibility_rows,
        "pool_manifest_sha256": hashlib.sha256(json.dumps(pool, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
    }
    write_json(OUT_ELIGIBILITY, order_eligibility)
    print(f"wrote {OUT_POOL}")
    print(f"wrote {OUT_ELIGIBILITY}")
    print("main order requirements:", order_eligibility["main_requirements"])


if __name__ == "__main__":
    main()
